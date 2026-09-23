import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

import config
from database import connect
from duplicate import DuplicateDetector
from parser import (
    extract_focused_links,
    extract_infobox_metadata,
    is_probable_film_article,
    parse_page,
)
from url_frontier import URLFrontier


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WikipediaMovieCrawler:
    def __init__(
        self,
        db_path,
        seed_url=config.SEED_URL,
        max_depth=config.MAX_DEPTH,
        max_pages=config.MAX_PAGES,
        crawl_delay=config.CRAWL_DELAY,
        request_timeout=config.REQUEST_TIMEOUT,
        max_retries=config.MAX_RETRIES,
    ):
        self.db_path = db_path
        self.seed_url = seed_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.crawl_delay = crawl_delay
        self.request_timeout = request_timeout
        self.max_retries = max_retries

        self.conn = connect(db_path)
        self.frontier = URLFrontier()
        self.duplicates = DuplicateDetector()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        })

        self.robots = RobotFileParser()
        self.robots.set_url(config.ROBOTS_URL)

        self.stats = Counter()
        self.depth_counts = Counter()
        self.type_counts = Counter()
        self.http_counts = Counter()
        self.filter_reasons = Counter()

    def close(self):
        self.conn.commit()
        self.conn.close()
        self.session.close()

    def load_robots(self):
        response = self.session.get(config.ROBOTS_URL, timeout=self.request_timeout)
        response.raise_for_status()
        self.robots.parse(response.text.splitlines())

        allowed = self.robots.can_fetch(config.USER_AGENT, self.seed_url)
        self.conn.execute(
            "INSERT INTO robots_checks(url,allowed,checked_at) VALUES (?,?,?)",
            (self.seed_url, 1 if allowed else 0, utc_now()),
        )
        self.conn.commit()

        print(f"[robots] {config.ROBOTS_URL}")
        print(f"[robots] Seed -> {'ALLOW' if allowed else 'BLOCK'}")
        return allowed

    def _restore_resume_state(self):
        """Resume without re-requesting pages already saved in SQLite."""
        rows = self.conn.execute(
            "SELECT url,depth,content_hash FROM pages ORDER BY id"
        ).fetchall()

        if not rows:
            return False

        for row in rows:
            self.frontier.mark_visited(row["url"])
            self.duplicates.add_hash(row["content_hash"])

        # Reconstruct discovered-but-not-yet-crawled URLs from hyperlink graph.
        pending = self.conn.execute(
            """
            SELECT l.target_url AS url, MIN(p.depth + 1) AS depth
            FROM links l
            JOIN pages p ON p.url = l.source_url
            LEFT JOIN pages t ON t.url = l.target_url
            WHERE t.url IS NULL
              AND p.depth < ?
            GROUP BY l.target_url
            ORDER BY depth, l.target_url
            """,
            (self.max_depth,),
        ).fetchall()

        for row in pending:
            self.frontier.add(row["url"], row["depth"])

        self.stats["pages_saved"] = len(rows)
        self.stats["movies_saved"] = self.conn.execute(
            "SELECT COUNT(*) FROM pages WHERE page_type='movie'"
        ).fetchone()[0]
        self.stats["links_saved"] = self.conn.execute(
            "SELECT COUNT(*) FROM links"
        ).fetchone()[0]

        for row in self.conn.execute(
            "SELECT depth,page_type,status_code,COUNT(*) n FROM pages GROUP BY depth,page_type,status_code"
        ):
            self.depth_counts[row["depth"]] += row["n"]
            self.type_counts[row["page_type"]] += row["n"]
            if row["status_code"] is not None:
                self.http_counts[row["status_code"]] += row["n"]

        print("=" * 76)
        print("RESUME MODE")
        print("=" * 76)
        print(f"Already saved pages   : {self.stats['pages_saved']:,}")
        print(f"Already saved movies  : {self.stats['movies_saved']:,}")
        print(f"Pending URLs restored : {len(self.frontier):,}")
        print("Existing pages will NOT be requested again.")
        print("=" * 76)
        return True

    def _retry_wait_seconds(self, response, attempt):
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1, min(int(float(retry_after)), 120))
            except (TypeError, ValueError):
                pass

        # Wikimedia recommends waiting at least 5 seconds when no Retry-After
        # is supplied. Increase gradually to avoid hammering the public site.
        return min(5 * (2 ** (attempt - 1)), 120)

    def _fetch(self, url):
        last_error = None
        last_response = None
        last_elapsed = None

        for attempt in range(1, self.max_retries + 1):
            start = time.perf_counter()
            try:
                response = self.session.get(
                    url,
                    timeout=self.request_timeout,
                    allow_redirects=True,
                )
                elapsed = time.perf_counter() - start
                last_response = response
                last_elapsed = elapsed

                if response.status_code in {429, 503}:
                    self.stats["rate_limited_responses"] += 1
                    if attempt < self.max_retries:
                        wait_s = self._retry_wait_seconds(response, attempt)
                        print(
                            f"[retry] HTTP {response.status_code} for {url} "
                            f"(attempt {attempt}/{self.max_retries}); "
                            f"waiting {wait_s}s"
                        )
                        time.sleep(wait_s)
                        continue

                return response, elapsed

            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait_s = min(5 * (2 ** (attempt - 1)), 60)
                    print(
                        f"[retry] {type(exc).__name__} for {url} "
                        f"(attempt {attempt}/{self.max_retries}); "
                        f"waiting {wait_s}s"
                    )
                    time.sleep(wait_s)
                    continue

        if last_response is not None:
            return last_response, last_elapsed

        raise last_error

    def _save_page(
        self, url, page_type, title, content, depth,
        status_code, response_time, content_hash, is_valid, probable_film
    ):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO pages
            (url,domain,page_type,title,content,depth,status_code,response_time,
             crawled_at,content_hash,is_valid,probable_film)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                url,
                urlparse(url).netloc,
                page_type,
                title,
                content,
                depth,
                status_code,
                response_time,
                utc_now(),
                content_hash,
                1 if is_valid else 0,
                1 if probable_film else 0,
            ),
        )

    def _save_links(self, source_url, links):
        for target in links:
            self.conn.execute(
                "INSERT OR IGNORE INTO links(source_url,target_url) VALUES (?,?)",
                (source_url, target),
            )

    def _save_movie_metadata(self, url, title, metadata, probable_film):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO movies
            (page_url,title,directed_by,release_date,running_time,country,language,probable_film)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                url,
                title,
                metadata.get("directed_by"),
                metadata.get("release_date"),
                metadata.get("running_time"),
                metadata.get("country"),
                metadata.get("language"),
                1 if probable_film else 0,
            ),
        )

    def _record_error(self, url, depth, error_type, message):
        self.conn.execute(
            "INSERT INTO errors(url,depth,error_type,message,occurred_at) VALUES (?,?,?,?,?)",
            (url, depth, error_type, str(message), utc_now()),
        )
        self.conn.commit()

    def crawl(self):
        print("=" * 76)
        print("SEG301 - WIKIPEDIA MOVIES FOCUSED WEB CRAWLER")
        print("=" * 76)
        print(f"Seed URL         : {self.seed_url}")
        print("Traversal        : BFS (deque URL Frontier)")
        print("HTTP client      : requests")
        print("HTML parser      : BeautifulSoup + lxml")
        print(f"Maximum depth    : {self.max_depth}")
        print(f"Maximum pages    : {self.max_pages:,}")
        print(f"Crawl delay      : {self.crawl_delay:.2f}s")
        print(f"Output DB        : {self.db_path}")
        print()

        if not self.load_robots():
            print("STOP: seed URL is disallowed by robots.txt.")
            return

        resumed = self._restore_resume_state()
        if not resumed:
            self.frontier.add(self.seed_url, 0)

        run_started = utc_now()
        cur = self.conn.execute(
            """
            INSERT INTO crawl_runs(started_at,seed_url,max_depth,max_pages)
            VALUES (?,?,?,?)
            """,
            (run_started, self.seed_url, self.max_depth, self.max_pages),
        )
        run_id = cur.lastrowid
        self.conn.commit()

        stop_reason = "URL Frontier is empty"

        try:
            while not self.frontier.empty():
                if self.stats["pages_saved"] >= self.max_pages:
                    stop_reason = "MAX_PAGES reached"
                    break

                item = self.frontier.get()
                if item is None:
                    break

                if self.frontier.is_visited(item.url):
                    continue

                if item.depth > self.max_depth:
                    self.stats["skipped_depth"] += 1
                    continue

                if not self.robots.can_fetch(config.USER_AGENT, item.url):
                    self.stats["robots_blocked"] += 1
                    self.frontier.mark_visited(item.url)
                    continue

                try:
                    response, elapsed = self._fetch(item.url)
                    self.stats["requests"] += 1
                    self.http_counts[response.status_code] += 1
                except requests.RequestException as exc:
                    self.stats["failed_requests"] += 1
                    self._record_error(item.url, item.depth, type(exc).__name__, exc)
                    self.frontier.mark_visited(item.url)
                    time.sleep(self.crawl_delay)
                    continue

                self.frontier.mark_visited(item.url)

                content_type = response.headers.get("Content-Type", "")
                if response.status_code != 200 or "text/html" not in content_type.lower():
                    self.stats["non_html_or_non_200"] += 1
                    self._record_error(
                        item.url, item.depth, "HTTP_OR_CONTENT_TYPE",
                        f"status={response.status_code}; content_type={content_type}",
                    )
                    time.sleep(self.crawl_delay)
                    continue

                html = response.text
                parsed = parse_page(html, item.url)
                title = parsed["title"]
                content = parsed["content"]
                page_type = parsed["page_type"]

                duplicate, content_hash = self.duplicates.is_duplicate(content)
                if duplicate:
                    self.stats["exact_duplicate_content"] += 1
                    # Do not save duplicate content as another document.
                    time.sleep(self.crawl_delay)
                    continue

                is_valid = bool(title) and len(content) >= config.MIN_CONTENT_CHARS
                probable_film = (
                    page_type == "movie" and is_probable_film_article(parsed)
                )

                self._save_page(
                    item.url,
                    page_type,
                    title,
                    content,
                    item.depth,
                    response.status_code,
                    elapsed,
                    content_hash,
                    is_valid,
                    probable_film,
                )

                self.stats["pages_saved"] += 1
                self.depth_counts[item.depth] += 1
                self.type_counts[page_type] += 1

                if page_type == "movie":
                    self.stats["movies_saved"] += 1
                    meta = extract_infobox_metadata(parsed["soup"])
                    self._save_movie_metadata(
                        item.url, title, meta, probable_film
                    )

                # Only discover deeper URLs when current depth permits it.
                if item.depth < self.max_depth:
                    links, rejected, reasons = extract_focused_links(
                        html, item.url
                    )
                    self.stats["filtered_links"] += rejected
                    self.filter_reasons.update(reasons)

                    self._save_links(item.url, links)
                    self.stats["links_saved"] += len(links)

                    for link in links:
                        if self.frontier.add(link, item.depth + 1):
                            self.stats["unique_urls_discovered"] += 1
                        else:
                            self.stats["duplicate_urls_skipped"] += 1

                self.conn.commit()

                if self.stats["pages_saved"] % 100 == 0:
                    print(
                        f"[progress] saved={self.stats['pages_saved']:,} "
                        f"movies={self.stats['movies_saved']:,} "
                        f"frontier={len(self.frontier):,} "
                        f"depth={item.depth}"
                    )

                # Be polite to the public Wikipedia server.
                time.sleep(self.crawl_delay)

        except KeyboardInterrupt:
            stop_reason = "Interrupted by user; safe to resume without --reset"
            print("\nInterrupted. Progress already stored in SQLite.")
        finally:
            self.conn.execute(
                """
                UPDATE crawl_runs
                SET finished_at=?,pages_saved=?,movies_saved=?,links_saved=?,
                    failed_requests=?,stop_reason=?
                WHERE id=?
                """,
                (
                    utc_now(),
                    self.stats["pages_saved"],
                    self.stats["movies_saved"],
                    self.stats["links_saved"],
                    self.stats["failed_requests"],
                    stop_reason,
                    run_id,
                ),
            )
            self.conn.commit()

        self.print_summary(stop_reason)

    def print_summary(self, stop_reason):
        print()
        print("=" * 76)
        print("CRAWLING SUMMARY")
        print("=" * 76)
        print(f"Pages saved             : {self.stats['pages_saved']:,}")
        print(f"Movie candidates saved  : {self.stats['movies_saved']:,}")
        print(f"Links saved             : {self.stats['links_saved']:,}")
        print(f"Failed requests         : {self.stats['failed_requests']:,}")
        print(f"Robots blocked          : {self.stats['robots_blocked']:,}")
        print(f"Duplicate URLs skipped  : {self.stats['duplicate_urls_skipped']:,}")
        print(f"Exact duplicate content : {self.stats['exact_duplicate_content']:,}")
        print(f"Filtered links          : {self.stats['filtered_links']:,}")
        print(f"Rate-limit responses    : {self.stats['rate_limited_responses']:,}")
        print(f"Stop reason             : {stop_reason}")

        for depth in sorted(self.depth_counts):
            print(f"Depth {depth:<2}               : {self.depth_counts[depth]:,}")

        for ptype in sorted(self.type_counts):
            print(f"Page type {ptype:<10}   : {self.type_counts[ptype]:,}")

        for status in sorted(self.http_counts):
            print(f"HTTP {status:<3}               : {self.http_counts[status]:,}")

        if self.filter_reasons:
            print("Filter reasons:")
            for key, value in self.filter_reasons.most_common():
                print(f" - {key:<24}: {value:,}")

        print("=" * 76)
