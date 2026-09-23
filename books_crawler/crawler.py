import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    SEED_URLS,
    ALLOWED_DOMAINS,
    MAX_PAGES,
    MAX_DEPTH,
    REQUEST_TIMEOUT,
    CRAWL_DELAY,
    USER_AGENT,
)
from database import Database
from parser import parse_page, is_allowed_url
from url_frontier import URLFrontier


class BooksCrawler:
    def __init__(self, db_path="data/crawler.db"):
        self.frontier = URLFrontier()
        self.visited = set()
        self.discovered = set()

        self.pages_crawled = 0
        self.failed_requests = 0
        self.skipped_urls = 0

        self.depth_stats = Counter()
        self.status_stats = Counter()

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.db = Database(db_path)

        for seed in SEED_URLS:
            if is_allowed_url(seed, ALLOWED_DOMAINS):
                self.frontier.add(seed, 0)
                self.discovered.add(seed)

    def crawl(self):
        print("=" * 60)
        print("BOOKS TO SCRAPE - SIMPLE WEB CRAWLER")
        print("=" * 60)

        while (
            not self.frontier.empty()
            and self.pages_crawled < MAX_PAGES
        ):
            item = self.frontier.pop()
            if item is None:
                break

            url, depth = item

            if url in self.visited:
                self.skipped_urls += 1
                continue

            if depth > MAX_DEPTH:
                self.skipped_urls += 1
                continue

            self.visited.add(url)

            print(f"[{self.pages_crawled + 1:03d}] "
                  f"Depth={depth}  {url}")

            self.crawl_url(url, depth)
            time.sleep(CRAWL_DELAY)

        self.print_summary()

    def crawl_url(self, url, depth):
        start = time.time()

        try:
            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            elapsed = time.time() - start
            status = response.status_code
            self.status_stats[status] += 1

            if status != 200:
                self.failed_requests += 1
                print(f"      HTTP {status}")
                return

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                self.skipped_urls += 1
                print("      Skipped: non-HTML")
                return

            parsed = parse_page(response.text, url)

            data = {
                "url": url,
                "domain": urlparse(url).netloc,
                "title": parsed["title"],
                "content": parsed["content"],
                "depth": depth,
                "status_code": status,
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "response_time": round(elapsed, 4),
                "book_title": parsed["book_title"],
                "price": parsed["price"],
                "rating": parsed["rating"],
                "category": parsed["category"],
            }

            self.db.save_page(data)

            for target in parsed["links"]:
                if not is_allowed_url(target, ALLOWED_DOMAINS):
                    self.skipped_urls += 1
                    continue

                self.db.save_link(url, target)

                self.discovered.add(target)

                if depth + 1 <= MAX_DEPTH:
                    self.frontier.add(target, depth + 1)

            self.pages_crawled += 1
            self.depth_stats[depth] += 1

            print(
                f"      OK | title={parsed['title'][:55]!r} "
                f"| links={len(parsed['links'])} "
                f"| {elapsed:.2f}s"
            )

        except requests.Timeout:
            self.failed_requests += 1
            self.status_stats["timeout"] += 1
            print("      ERROR: timeout")

        except requests.RequestException as exc:
            self.failed_requests += 1
            self.status_stats["request_error"] += 1
            print(f"      ERROR: {exc}")

    def print_summary(self):
        print("\n" + "=" * 60)
        print("CRAWL SUMMARY")
        print("=" * 60)
        print(f"Pages crawled       : {self.pages_crawled}")
        print(f"Unique URLs found   : {len(self.discovered)}")
        print(f"Skipped URLs        : {self.skipped_urls}")
        print(f"Failed requests     : {self.failed_requests}")
        print(f"Maximum depth       : {MAX_DEPTH}")
        print(f"Frontier remaining  : {len(self.frontier)}")

        print("\nDepth statistics:")
        for depth in sorted(self.depth_stats):
            print(f"  Depth {depth}: {self.depth_stats[depth]}")

        print("\nHTTP statistics:")
        for status, count in self.status_stats.items():
            print(f"  {status}: {count}")

        print("=" * 60)

    def close(self):
        self.db.close()
        self.session.close()
