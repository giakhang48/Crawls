import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from config import (
    TOPIC,
    SEED_URLS,
    ALLOWED_DOMAINS,
    MAX_DEPTH,
    MAX_PAGES,
    REQUEST_TIMEOUT,
    CRAWL_DELAY,
    USER_AGENT,
    EXTRA_HEADERS,
    DATABASE_PATH,
)
from database import CrawlerDB
from parser import normalize_url, extract_page_info, extract_links
from url_frontier import URLFrontier


class FocusedCrawler:
    def __init__(self):
        self.frontier = URLFrontier()
        self.visited = set()
        self.discovered = set()
        self.failed_requests = 0
        self.skipped_urls = 0
        self.pages_crawled = 0
        self.depth_counts = Counter()
        self.status_counts = Counter()
        self.response_times = []
        self.robot_parsers = {}

        self.session = requests.Session()
        headers = {"User-Agent": USER_AGENT}
        headers.update(EXTRA_HEADERS)
        self.session.headers.update(headers)

        self.db = CrawlerDB(DATABASE_PATH)

    def print_config(self):
        print("=" * 60)
        print("CRAWLER CONFIGURATION")
        print("=" * 60)
        print(f"Topic           : {TOPIC}")
        print(f"Seed URLs       : {len(SEED_URLS)}")
        for url in SEED_URLS:
            print(f"  - {url}")
        print("Allowed Domains :")
        for d in sorted(ALLOWED_DOMAINS):
            print(f"  - {d}")
        print(f"Maximum Depth   : {MAX_DEPTH}")
        print(f"Maximum Pages   : {MAX_PAGES}")
        print(f"Request Timeout : {REQUEST_TIMEOUT} seconds")
        print(f"Crawl Delay     : {CRAWL_DELAY} seconds")
        print("=" * 60)

    def get_robot_parser(self, url: str):
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin in self.robot_parsers:
            return self.robot_parsers[origin]

        robots_url = f"{origin}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)

        try:
            # RobotFileParser.read() có User-Agent riêng khó kiểm soát,
            # nên tự tải bằng requests rồi parse.
            response = self.session.get(robots_url, timeout=REQUEST_TIMEOUT)
            if response.ok:
                rp.parse(response.text.splitlines())
            else:
                print(
                    f"[ROBOTS] Could not read {robots_url} "
                    f"(HTTP {response.status_code}); skip domain for safety."
                )
                self.robot_parsers[origin] = None
                return None
        except requests.RequestException as exc:
            print(f"[ROBOTS] Failed: {robots_url}: {exc}")
            self.robot_parsers[origin] = None
            return None

        self.robot_parsers[origin] = rp
        return rp

    def allowed_by_robots(self, url: str) -> bool:
        rp = self.get_robot_parser(url)
        if rp is None:
            return False
        return rp.can_fetch(USER_AGENT, url)

    def add_seed_urls(self):
        for seed in SEED_URLS:
            seed = normalize_url(seed)
            if seed not in self.discovered:
                self.frontier.add(seed, 0)
                self.discovered.add(seed)

    def crawl(self):
        self.print_config()
        self.add_seed_urls()

        while not self.frontier.empty() and self.pages_crawled < MAX_PAGES:
            url, depth = self.frontier.pop()

            if url in self.visited:
                self.skipped_urls += 1
                continue

            self.visited.add(url)

            if depth > MAX_DEPTH:
                self.skipped_urls += 1
                continue

            if not self.allowed_by_robots(url):
                print(f"[SKIP robots.txt] {url}")
                self.skipped_urls += 1
                continue

            print()
            print(f"[Crawl #{self.pages_crawled + 1:03d}]")
            print(f"Depth : {depth}")
            print(f"URL   : {url}")

            started = time.perf_counter()

            try:
                response = self.session.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
                elapsed = time.perf_counter() - started
                self.response_times.append(elapsed)

                status = response.status_code
                self.status_counts[status] += 1

                print(f"Status: {status}")
                print(f"Time  : {elapsed:.2f} sec")

                content_type = response.headers.get("Content-Type", "").lower()

                # Theo bài: request lỗi phải được ghi nhận, không làm cả crawler dừng.
                if status != 200:
                    self.failed_requests += 1
                    time.sleep(CRAWL_DELAY)
                    continue

                if "text/html" not in content_type:
                    print(f"[SKIP non-HTML] {content_type}")
                    self.skipped_urls += 1
                    time.sleep(CRAWL_DELAY)
                    continue

                final_url = normalize_url(response.url)
                soup = BeautifulSoup(response.text, "html.parser")

                page = extract_page_info(
                    soup=soup,
                    url=final_url,
                    depth=depth,
                    status_code=status,
                )
                page["crawled_at"] = datetime.now(timezone.utc).isoformat()

                self.db.save_page(page)
                self.pages_crawled += 1
                self.depth_counts[depth] += 1

                links = extract_links(soup, final_url)
                print(f"Title : {page['title'][:100]}")
                if page.get("film_name"):
                    print(
                        f"Film  : {page['film_name']} "
                        f"({page.get('release_year') or '?'}) "
                        f"- dir. {page.get('director') or '?'} "
                        f"- rating {page.get('rating_value') or '?'}"
                    )
                print(f"Links : {len(links)}")

                for target in links:
                    self.db.save_link(final_url, target)

                    if target not in self.discovered:
                        self.discovered.add(target)

                    new_depth = depth + 1

                    if new_depth <= MAX_DEPTH and target not in self.visited:
                        self.frontier.add(target, new_depth)

                self.db.commit()

            except requests.Timeout:
                self.failed_requests += 1
                print("[ERROR] Request timeout")
            except requests.RequestException as exc:
                self.failed_requests += 1
                print(f"[ERROR] Request failed: {exc}")
            except Exception as exc:
                self.failed_requests += 1
                print(f"[ERROR] Unexpected error: {exc}")

            time.sleep(CRAWL_DELAY)

        self.print_summary()
        self.db.close()

    def print_summary(self):
        print()
        print("=" * 60)
        print("CRAWLING SUMMARY")
        print("=" * 60)
        print(f"Topic                  : {TOPIC}")
        print(f"Seed URLs              : {len(SEED_URLS)}")
        print(f"Pages Crawled          : {self.pages_crawled}")
        print(f"Unique URLs Discovered : {len(self.discovered)}")
        print(f"Skipped URLs           : {self.skipped_urls}")
        print(f"Failed Requests        : {self.failed_requests}")
        print(f"Maximum Depth          : {MAX_DEPTH}")

        for depth in sorted(self.depth_counts):
            print(f"Depth {depth:<2}                : {self.depth_counts[depth]} pages")

        for status in sorted(self.status_counts):
            print(f"HTTP {status:<3}                : {self.status_counts[status]}")

        if self.response_times:
            avg = sum(self.response_times) / len(self.response_times)
            print(f"Average Response Time  : {avg:.2f} sec")

        print("=" * 60)
