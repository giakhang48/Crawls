"""Task 3, 6, 9: ghép các bước thành crawler BFS đơn luồng."""
import json
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit
import requests
from database import connect_db, save_page, save_link, save_event
from parser import normalize_url, is_allowed, parse_page
from robots import RobotsRules
from url_frontier import URLFrontier


def now():
    return datetime.now(timezone.utc).isoformat()


class Crawler:
    def __init__(self, config, output_dir, session=None):
        self.config = config
        self.output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        self.db = connect_db(output_dir / "crawler.db")
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})
        self.frontier = URLFrontier()
        self.last_request = {}
        self.robot_cache = {}
        self.blocked_hosts = set()
        self.discovered = set()
        self.skips = Counter()
        self.attempts = 0
        self.pages = 0
        self.failures = 0
        self.statuses = Counter()

    def request(self, url, delay):
        host = urlsplit(url).netloc
        wait = delay - (time.monotonic() - self.last_request.get(host, -float("inf")))
        if wait > 0:
            time.sleep(wait)
        try:
            # Redirect là response riêng, không đi theo một URL chưa kiểm tra.
            return self.session.get(url, timeout=self.config.REQUEST_TIMEOUT, allow_redirects=False)
        finally:
            self.last_request[host] = time.monotonic()

    def get_robots(self, url):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin in self.robot_cache:
            return self.robot_cache[origin]
        robot_url = origin + "/robots.txt"
        status, message, rules = None, "", None
        start = time.monotonic()
        try:
            response = self.request(robot_url, self.config.CRAWL_DELAY)
            status = response.status_code
            if status == 200 and "<html" not in response.text[:1000].lower():
                rules = RobotsRules(response.text, self.config.USER_AGENT)
                message = "Robots loaded"
            elif status in {404, 410}:
                rules = RobotsRules("", self.config.USER_AGENT)
                message = "No robots.txt; still check website Terms of Use"
            else:
                message = "Robots unavailable: skip origin (no automatic redirect/retry)"
        except requests.RequestException as error:
            message = str(error)
        save_event(self.db, robot_url, None, status, "robots", message,
                   time.monotonic() - start, now())
        self.robot_cache[origin] = rules
        print(f"[robots] {origin}: {status} | {message}")
        return rules

    def run(self):
        c = self.config
        reason = "frontier_empty"
        for seed in c.SEED_URLS:
            url = normalize_url(seed, seed)
            if url and is_allowed(url, c):
                self.discovered.add(url)
                self.frontier.add(url, 0)
            else:
                self.skips["invalid_seed"] += 1
        try:
            while self.frontier:
                if self.pages >= c.MAX_PAGES:
                    reason = "max_pages"
                    break
                if self.attempts >= c.MAX_REQUESTS:
                    reason = "max_requests"
                    break
                url, depth = self.frontier.pop()
                host = urlsplit(url).netloc
                if host in self.blocked_hosts:
                    self.skips["blocked_host"] += 1
                    continue
                rules = self.get_robots(url)
                if rules is None or not rules.allowed(url):
                    self.skips["robots"] += 1
                    save_event(self.db, url, depth, None, "skip", "robots", 0, now())
                    continue
                self.attempts += 1
                print(f"\n[Crawl #{self.attempts:03}] Depth={depth} | {url}")
                status = None
                start = time.monotonic()
                try:
                    response = self.request(url, max(c.CRAWL_DELAY, rules.delay))
                    elapsed = response.elapsed.total_seconds()
                    status = response.status_code
                    self.statuses[status] += 1
                    if status != 200:
                        self.failures += 1
                        if status in {401, 403, 429}:
                            self.blocked_hosts.add(host)
                        message = f"HTTP {status}; Location={response.headers.get('Location', '')}"
                        save_event(self.db, url, depth, status, "http_error", message, elapsed, now())
                        print(message)
                        continue
                    media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    if media_type not in {"text/html", "application/xhtml+xml"}:
                        self.skips["non_html"] += 1
                        save_event(self.db, url, depth, status, "skip", "non_html", elapsed, now())
                        continue
                    title, content, hrefs, base = parse_page(response.content, url)
                    if any(marker in title.lower() for marker in ("just a moment", "access denied", "verify you are human")):
                        self.failures += 1
                        self.blocked_hosts.add(host)
                        save_event(self.db, url, depth, status, "challenge", title, elapsed, now())
                        continue
                    save_page(self.db, dict(url=url, domain=host, title=title, content=content,
                        depth=depth, status_code=status, crawled_at=now(), response_time=elapsed))
                    self.pages += 1
                    valid_links = set()
                    for href in hrefs:
                        target = normalize_url(href, base)
                        if not target or not is_allowed(target, c):
                            self.skips["url_filter"] += 1
                            continue
                        self.discovered.add(target)
                        valid_links.add(target)
                        save_link(self.db, url, target)
                        if depth >= c.MAX_DEPTH:
                            self.skips["depth_limit"] += 1
                        elif not self.frontier.add(target, depth + 1):
                            self.skips["duplicate"] += 1
                    self.db.commit()
                    print(f"Status: {status} | Title: {title}\nLinks: {len(valid_links)} | Time: {elapsed:.2f}s")
                except requests.RequestException as error:
                    self.failures += 1
                    save_event(self.db, url, depth, status, "request_error", str(error),
                               time.monotonic() - start, now())
                    print(f"Request failed: {error}")
        except KeyboardInterrupt:
            reason = "user_interrupt"
            print("\nStopped by user; keeping saved results.")
        finally:
            summary = self.write_summary(reason)
            self.db.close()
            self.session.close()
        return summary

    def write_summary(self, reason):
        by_depth = dict(self.db.execute("SELECT depth, COUNT(*) FROM pages GROUP BY depth"))
        by_domain = dict(self.db.execute("SELECT domain, COUNT(*) FROM pages GROUP BY domain"))
        summary = {
            "topic": self.config.TOPIC, "seed_urls": self.config.SEED_URLS,
            "pages_crawled": self.pages, "page_requests": self.attempts,
            "unique_urls_discovered": len(self.discovered),
            "skipped_url_occurrences": sum(self.skips.values()),
            "skip_reasons": dict(self.skips), "failed_requests": self.failures,
            "maximum_depth_configured": self.config.MAX_DEPTH,
            "maximum_depth_reached": max(by_depth, default=None),
            "by_depth": by_depth, "by_domain": by_domain,
            "http_statuses": dict(self.statuses), "stop_reason": reason,
            "frontier_remaining": len(self.frontier.queue),
            "configured_domains": sorted(self.config.ALLOWED_DOMAINS),
            "domains_collected": len(by_domain),
            "all_configured_domains_have_pages": bool(self.config.ALLOWED_DOMAINS)
                and self.config.ALLOWED_DOMAINS.issubset(by_domain),
        }
        text = json.dumps(summary, ensure_ascii=False, indent=2)
        (self.output_dir / "summary.json").write_text(text, encoding="utf-8")
        report = "# Kết quả crawl thực tế\n\n```json\n" + text + "\n```\n"
        report += "\nPhạm vi cá nhân: một domain Metacritic. Yêu cầu ít nhất hai domain áp dụng cho bài chung của nhóm.\n"
        if self.pages == 0:
            report += "\nChưa thu thập được trang HTML thành công. Xem bảng events để tìm nguyên nhân.\n"
        else:
            report += "\nĐã lưu trang HTML; cần xem title/content để xác nhận đúng nội dung phim trước khi nộp.\n"
        (self.output_dir / "RESULTS.md").write_text(report, encoding="utf-8")
        print("\n========== CRAWLING SUMMARY ==========\n" + text)
        print(f"\nOutput: {self.output_dir}")
        return summary
