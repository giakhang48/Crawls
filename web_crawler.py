from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import math
import sqlite3
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from database import connect, reset_database
from duplicate import DuplicateDetector
from parser import extract_links_detailed, extract_movie_metadata, extract_page, normalize_url
from url_frontier import URLFrontier


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class FocusedWebCrawler:
    """Real HTTP focused crawler with level-synchronous BFS.

    Concurrency is only used INSIDE one BFS depth. URLs at depth d+1 are never
    requested until all queued URLs at depth d have been processed.
    """

    def __init__(
        self,
        seed_url,
        allowed_netloc,
        db_path,
        source_movie_count,
        expected_listing_pages,
        expected_total_pages,
        max_depth=2,
        max_pages=None,
        workers=16,
        fetch_batch_size=512,
        request_timeout=20,
        crawl_delay=0.0,
        user_agent="SEG301-FocusedCrawler/1.0",
        request_retries=4,
        retry_backoff=0.25,
        reset=False,
        verbose_every=10000,
    ):
        self.seed_url = normalize_url(seed_url)
        self.allowed_netlocs = {allowed_netloc.lower()}
        self.db_path = Path(db_path)
        self.source_movie_count = int(source_movie_count)
        self.expected_listing_pages = int(expected_listing_pages)
        self.expected_total_pages = int(expected_total_pages)
        self.max_depth = int(max_depth)
        self.max_pages = int(max_pages or expected_total_pages)
        self.workers = max(1, int(workers))
        self.fetch_batch_size = max(self.workers, int(fetch_batch_size))
        self.request_timeout = request_timeout
        self.crawl_delay = crawl_delay
        self.user_agent = user_agent
        self.request_retries = max(1, int(request_retries))
        self.retry_backoff = max(0.0, float(retry_backoff))
        self.verbose_every = max(1, int(verbose_every))

        if reset:
            reset_database(self.db_path)
        self.conn = connect(self.db_path)
        self.frontier = URLFrontier()
        self.duplicates = DuplicateDetector()
        self._thread_local = threading.local()
        self._robot_parser = None

        self.pages_requested = 0
        self.pages_saved = 0
        self.movie_pages_saved = 0
        self.links_saved = 0
        self.unique_urls_discovered = 0
        self.filtered_links = 0
        self.skipped_urls = 0
        self.duplicate_contents = 0
        self.failed_requests = 0
        self.depth_counts = defaultdict(int)
        self.http_counts = Counter()
        self.page_type_counts = Counter()

    def _session(self):
        if not hasattr(self._thread_local, "session"):
            s = requests.Session()
            s.headers.update({"User-Agent": self.user_agent})
            self._thread_local.session = s
        return self._thread_local.session

    def _load_robots(self):
        parsed = urlparse(self.seed_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        response = requests.get(robots_url, headers={"User-Agent": self.user_agent}, timeout=self.request_timeout)
        rp = RobotFileParser()
        rp.set_url(robots_url)
        if response.status_code == 200:
            rp.parse(response.text.splitlines())
        else:
            rp.parse([])
        allowed = rp.can_fetch(self.user_agent, self.seed_url)
        self.conn.execute(
            "INSERT INTO robots_checks(checked_at,robots_url,target_url,allowed,note) VALUES (?,?,?,?,?)",
            (utc_now(), robots_url, self.seed_url, int(allowed), f"HTTP {response.status_code}"),
        )
        self.conn.commit()
        self._robot_parser = rp
        print(f"[robots] {robots_url} -> {'ALLOW' if allowed else 'BLOCK'}")
        return allowed

    def _allowed_by_robots(self, url):
        return True if self._robot_parser is None else self._robot_parser.can_fetch(self.user_agent, url)

    def _fetch(self, item):
        url, depth = item
        started = time.perf_counter()
        last_error = None

        for attempt in range(1, self.request_retries + 1):
            try:
                # Separate connect/read timeouts. The mirror is local, so connect
                # should be immediate; a generous read timeout protects large
                # listing pages on slower Windows/antivirus setups.
                response = self._session().get(
                    url,
                    timeout=(5, self.request_timeout),
                )
                elapsed = time.perf_counter() - started
                content_type = response.headers.get("Content-Type", "")
                result = {
                    "url": url,
                    "depth": depth,
                    "status": response.status_code,
                    "elapsed": elapsed,
                    "content_type": content_type,
                    "error": None,
                    "attempts": attempt,
                }
                if response.status_code == 200 and "text/html" in content_type.lower():
                    html = response.text
                    page = extract_page(html)
                    links, filter_stats = extract_links_detailed(html, url, self.allowed_netlocs)
                    result.update({"html": html, "page": page, "links": links, "filter_stats": filter_stats})
                return result
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                # Drop the thread-local Session after a broken/aborted socket so
                # the next attempt gets a fresh connection pool.
                try:
                    self._thread_local.session.close()
                    del self._thread_local.session
                except AttributeError:
                    pass
                if attempt < self.request_retries:
                    time.sleep(self.retry_backoff * attempt)
                    continue
            except requests.RequestException as exc:
                last_error = exc
                break

        return {
            "url": url,
            "depth": depth,
            "error": f"{type(last_error).__name__}: {last_error}",
            "elapsed": time.perf_counter() - started,
            "attempts": self.request_retries,
        }

    @staticmethod
    def _chunks(items, size=5000):
        for i in range(0, len(items), size):
            yield items[i:i+size]

    def _record_error(self, url, kind, message):
        self.conn.execute(
            "INSERT INTO errors(occurred_at,url,error_type,message) VALUES (?,?,?,?)",
            (utc_now(), url, kind, message),
        )

    def _flush_rows(self, pages, links, movies):
        if pages:
            self.conn.executemany(
                """INSERT OR REPLACE INTO pages
                   (url,domain,source_domain,canonical_url,page_type,title,content,depth,
                    status_code,response_time,crawled_at,content_hash,is_valid)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                pages,
            )
        if links:
            for chunk in self._chunks(links, 5000):
                before = self.conn.total_changes
                self.conn.executemany(
                    "INSERT OR IGNORE INTO links(source_url,target_url) VALUES (?,?)", chunk
                )
                self.links_saved += self.conn.total_changes - before
        if movies:
            self.conn.executemany(
                """INSERT OR REPLACE INTO movies
                   (tconst,primary_title,original_title,start_year,runtime_minutes,genres,
                    average_rating,num_votes,crawled_url,canonical_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                movies,
            )
        self.conn.commit()

    def crawl(self):
        if urlparse(self.seed_url).netloc.lower() not in self.allowed_netlocs:
            raise ValueError("Seed URL is outside allowed domain/netloc.")

        print("=" * 78)
        print("SEG301 - IMDb LOCAL MIRROR REAL WEB CRAWLER")
        print("=" * 78)
        print(f"Seed URL               : {self.seed_url}")
        print(f"Allowed netloc         : {', '.join(self.allowed_netlocs)}")
        print("Traversal               : BFS (level-synchronous deque frontier)")
        print("HTTP client             : requests")
        print("HTML parser             : BeautifulSoup")
        print(f"Maximum depth           : {self.max_depth}")
        print(f"Maximum pages           : {self.max_pages:,}")
        print(f"Workers                 : {self.workers}")
        print(f"Request timeout         : {self.request_timeout}s")
        print(f"Retries/request         : {self.request_retries}")
        print(f"Expected movie pages    : {self.source_movie_count:,}")
        print(f"Expected listing pages  : {self.expected_listing_pages:,}")
        print(f"Expected total pages    : {self.expected_total_pages:,}")
        print(f"Output DB               : {self.db_path}")
        print()

        if not self._load_robots():
            raise RuntimeError("Local mirror robots.txt unexpectedly blocked the crawler.")

        started_at = utc_now()
        run_id = self.conn.execute(
            """INSERT INTO crawl_runs
               (started_at,mode,seed_url,max_depth,max_pages,workers,source_movie_count,
                expected_listing_pages,expected_total_pages)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (started_at, "local_mirror_real_web_crawl", self.seed_url, self.max_depth,
             self.max_pages, self.workers, self.source_movie_count,
             self.expected_listing_pages, self.expected_total_pages),
        ).lastrowid
        self.conn.commit()

        self.frontier.add(self.seed_url, 0)
        self.unique_urls_discovered = 1
        stop_reason = "URL Frontier is empty"
        last_progress = 0

        try:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                while not self.frontier.empty():
                    remaining = self.max_pages - self.pages_requested
                    if remaining <= 0:
                        stop_reason = "MAX_PAGES reached"
                        break

                    batch_size = min(self.fetch_batch_size, remaining)
                    batch = self.frontier.get_same_depth_batch(batch_size)
                    if not batch:
                        break
                    current_depth = batch[0][1]

                    request_batch = []
                    for url, depth in batch:
                        if url in self.frontier.visited:
                            self.skipped_urls += 1
                            continue
                        self.frontier.mark_visited(url)
                        if depth > self.max_depth:
                            self.skipped_urls += 1
                            continue
                        if not self._allowed_by_robots(url):
                            self.skipped_urls += 1
                            continue
                        request_batch.append((url, depth))

                    if not request_batch:
                        continue

                    self.pages_requested += len(request_batch)
                    results = executor.map(self._fetch, request_batch)

                    page_rows, link_rows, movie_rows = [], [], []
                    for result in results:
                        url = result["url"]
                        depth = result["depth"]
                        if result.get("error"):
                            self.failed_requests += 1
                            self._record_error(url, "request", result["error"])
                            continue

                        status = result["status"]
                        self.http_counts[status] += 1
                        if status != 200:
                            self.failed_requests += 1
                            self._record_error(url, f"HTTP_{status}", f"HTTP {status}")
                            continue
                        if "text/html" not in result["content_type"].lower():
                            self.skipped_urls += 1
                            continue

                        html = result["html"]
                        if self.duplicates.is_duplicate(html):
                            self.duplicate_contents += 1
                            continue

                        page = result["page"]
                        links = result["links"]
                        filter_stats = result["filter_stats"]
                        self.filtered_links += max(0, filter_stats.get("raw", 0) - filter_stats.get("accepted", 0))

                        valid = int(bool(page["title"].strip() and page["content"].strip()))
                        domain = urlparse(url).netloc.lower()
                        fp = DuplicateDetector.hexdigest(html)
                        page_rows.append((
                            url, domain, "imdb.com", page.get("canonical_url") or None,
                            page["page_type"], page["title"], page["content"], depth,
                            status, result["elapsed"], utc_now(), fp, valid,
                        ))
                        link_rows.extend((url, target) for target in links)

                        metadata = extract_movie_metadata(page)
                        if metadata:
                            movie_rows.append((
                                metadata["tconst"], metadata["primary_title"], metadata["original_title"],
                                metadata["start_year"], metadata["runtime_minutes"], metadata["genres"],
                                metadata["average_rating"], metadata["num_votes"], url,
                                metadata["canonical_url"],
                            ))
                            self.movie_pages_saved += 1

                        self.pages_saved += 1
                        self.depth_counts[depth] += 1
                        self.page_type_counts[page["page_type"]] += 1

                        if depth < self.max_depth:
                            for link in links:
                                if self.frontier.add(link, depth + 1):
                                    self.unique_urls_discovered += 1

                    self._flush_rows(page_rows, link_rows, movie_rows)

                    if self.pages_saved - last_progress >= self.verbose_every or current_depth < 2:
                        last_progress = self.pages_saved
                        print(
                            f"[progress] depth={current_depth} requested={self.pages_requested:,} "
                            f"saved={self.pages_saved:,} movies={self.movie_pages_saved:,} "
                            f"frontier={len(self.frontier):,}"
                        )
                    if self.crawl_delay:
                        time.sleep(self.crawl_delay)

            if self.frontier.empty() and self.pages_requested < self.max_pages:
                stop_reason = "URL Frontier is empty"
            elif self.frontier.empty() and self.pages_requested == self.max_pages:
                # If both conditions become true together, frontier exhaustion is the
                # stronger completeness signal.
                stop_reason = "URL Frontier is empty"

            self.conn.execute(
                """UPDATE crawl_runs SET finished_at=?,pages_requested=?,pages_saved=?,
                   movie_pages_saved=?,links_saved=?,unique_urls_discovered=?,filtered_links=?,
                   skipped_urls=?,duplicate_contents=?,failed_requests=?,stop_reason=? WHERE id=?""",
                (utc_now(), self.pages_requested, self.pages_saved, self.movie_pages_saved,
                 self.links_saved, self.unique_urls_discovered, self.filtered_links,
                 self.skipped_urls, self.duplicate_contents, self.failed_requests,
                 stop_reason, run_id),
            )
            self.conn.commit()
            self.print_summary(stop_reason)
            return self.summary(stop_reason)
        except Exception as exc:
            self.conn.execute(
                "UPDATE crawl_runs SET finished_at=?,stop_reason=? WHERE id=?",
                (utc_now(), f"FAILED: {exc}", run_id),
            )
            self.conn.commit()
            raise

    def summary(self, stop_reason):
        return {
            "pages_requested": self.pages_requested,
            "pages_saved": self.pages_saved,
            "movie_pages_saved": self.movie_pages_saved,
            "links_saved": self.links_saved,
            "unique_urls_discovered": self.unique_urls_discovered,
            "filtered_links": self.filtered_links,
            "skipped_urls": self.skipped_urls,
            "duplicate_contents": self.duplicate_contents,
            "failed_requests": self.failed_requests,
            "depth_counts": dict(self.depth_counts),
            "page_type_counts": dict(self.page_type_counts),
            "http_counts": dict(self.http_counts),
            "stop_reason": stop_reason,
        }

    def print_summary(self, stop_reason):
        print()
        print("=" * 78)
        print("CRAWLING SUMMARY")
        print("=" * 78)
        print(f"Pages requested        : {self.pages_requested:,}")
        print(f"Pages saved            : {self.pages_saved:,}")
        print(f"Movie pages saved      : {self.movie_pages_saved:,}")
        print(f"Links saved            : {self.links_saved:,}")
        print(f"Unique URLs discovered : {self.unique_urls_discovered:,}")
        print(f"Filtered links         : {self.filtered_links:,}")
        print(f"Skipped URLs           : {self.skipped_urls:,}")
        print(f"Exact duplicate HTML   : {self.duplicate_contents:,}")
        print(f"Failed requests        : {self.failed_requests:,}")
        print(f"Stop reason            : {stop_reason}")
        for depth in sorted(self.depth_counts):
            print(f"Depth {depth:<2}              : {self.depth_counts[depth]:,}")
        for kind in sorted(self.page_type_counts):
            print(f"Page type {kind:<9} : {self.page_type_counts[kind]:,}")
        for status in sorted(self.http_counts):
            print(f"HTTP {status:<3}              : {self.http_counts[status]:,}")
        print("=" * 78)

    def close(self):
        self.conn.close()
