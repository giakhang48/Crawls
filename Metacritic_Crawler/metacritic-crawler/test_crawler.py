"""Kiểm thử offline bằng server cục bộ; KHÔNG phải dữ liệu phim đã crawl."""
import io
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from crawler import Crawler
from parser import normalize_url, is_allowed
import config
from robots import RobotsRules


class CrawlerTests(unittest.TestCase):
    def test_metacritic_scope(self):
        self.assertEqual(config.ALLOWED_DOMAINS, {"www.metacritic.com"})
        self.assertEqual(len(config.SEED_URLS), 1)
        self.assertTrue(is_allowed(config.SEED_URLS[0], config))
        self.assertTrue(is_allowed("https://www.metacritic.com/movie/inception/", config))
        for url in ("https://www.metacritic.com/game/test/",
                    "https://www.metacritic.com/tv/test/",
                    "https://www.rottentomatoes.com/m/inception",
                    "https://www.metacritic.com.evil.test/movie/test/"):
            self.assertFalse(is_allowed(url, config))

    def test_normalization(self):
        self.assertEqual(normalize_url("/m/a?utm_source=test&page=2#cast", "https://EXAMPLE.com/"),
                         "https://example.com/m/a?page=2")
        self.assertIsNone(normalize_url("mailto:a@example.com", "https://example.com"))
        self.assertIsNone(normalize_url("http://example.com:bad/", "https://example.com"))

    def test_robots_wildcard_and_agent(self):
        rules = RobotsRules("User-agent: OtherBot\nDisallow: /\nUser-agent: *\n"
                            "Disallow: /private/\nAllow: /private/public/\n"
                            "Disallow: /*/pictures$\nCrawl-delay: 3", "SEG301MovieCrawler/1.0")
        self.assertTrue(rules.allowed("https://example.com/film/a"))
        self.assertFalse(rules.allowed("https://example.com/private/a"))
        self.assertTrue(rules.allowed("https://example.com/private/public/a"))
        self.assertFalse(rules.allowed("https://example.com/m/a/pictures"))
        self.assertEqual(rules.delay, 3)

    def test_bfs_depth_dedup_errors_and_sqlite(self):
        hits = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                hits.append((self.headers["Host"], self.path))
                if self.path == "/robots.txt":
                    body = b"User-agent: *\nDisallow: /private/"
                    media = "text/plain"
                    status = 200
                elif self.path == "/":
                    body = (b'<title>Movie list</title><main><a href="/m/a">A</a>'
                            b'<a href="/m/a#cast">Duplicate</a><a href="/m/b">B</a>'
                            b'<a href="/missing">Missing</a><a href="/private/x">Private</a>'
                            b'<a href="/tv/a">TV</a><a href="https://outside.test/m/a">Out</a></main>')
                    media, status = "text/html", 200
                elif self.path == "/missing":
                    body, media, status = b"Not Found", "text/html", 404
                else:
                    body = '<title>Phim thử</title><main>Nội dung<script>NOISE</script><a href="/m/deep">Deep</a></main>'.encode()
                    media, status = "text/html; charset=utf-8", 200
                self.send_response(status)
                self.send_header("Content-Type", media)
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_port
        hosts = {f"127.0.0.1:{port}"}
        cfg = SimpleNamespace(TOPIC="OFFLINE TEST ONLY", SEED_URLS=[f"http://{h}/" for h in sorted(hosts)],
            ALLOWED_DOMAINS=hosts, PATH_PATTERNS={h: [r"/", r"/m/.*", r"/missing", r"/private/.*"] for h in hosts},
            MAX_PAGES=100, MAX_DEPTH=1, MAX_REQUESTS=30, REQUEST_TIMEOUT=2,
            CRAWL_DELAY=0, USER_AGENT="SEG301MovieCrawler/1.0")
        try:
            with tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                with redirect_stdout(io.StringIO()):
                    result = Crawler(cfg, out).run()
                self.assertEqual(result["pages_crawled"], 3)
                self.assertEqual(result["failed_requests"], 1)
                self.assertTrue(result["all_configured_domains_have_pages"])
                self.assertEqual(result["domains_collected"], 1)
                self.assertNotIn("at_least_two_domains_collected", result)
                self.assertEqual(result["http_statuses"], {200: 3, 404: 1})
                self.assertEqual(result["skip_reasons"]["robots"], 1)
                self.assertFalse(any(p in {"/private/x", "/m/deep", "/tv/a"} for _, p in hits))
                self.assertEqual(len(hits), len(set(hits)))
                with sqlite3.connect(out / "crawler.db") as db:
                    depths = [r[0] for r in db.execute("SELECT depth FROM pages ORDER BY id")]
                    self.assertEqual(depths, [0, 1, 1])
                    contents = [r[0] for r in db.execute("SELECT content FROM pages")]
                    self.assertTrue(any("Nội dung" in s for s in contents))
                    self.assertFalse(any("NOISE" in s for s in contents))
                    self.assertGreater(db.execute("SELECT COUNT(*) FROM links").fetchone()[0], 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
