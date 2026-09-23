import sqlite3
import tempfile
import unittest
from pathlib import Path

from mirror_server import MirrorServer
from validate import validate_crawl
from web_crawler import FocusedWebCrawler


class EndToEndTest(unittest.TestCase):
    def test_real_http_bfs_crawl(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source = td / "source.db"
            output = td / "crawl.db"

            conn = sqlite3.connect(source)
            conn.execute("""CREATE TABLE movies(
                tconst TEXT PRIMARY KEY, title_type TEXT, primary_title TEXT,
                original_title TEXT, is_adult INTEGER, start_year INTEGER,
                end_year INTEGER, runtime_minutes INTEGER, genres TEXT,
                average_rating REAL, num_votes INTEGER)""")
            rows = []
            for i in range(23):
                tconst = f"tt{i:07d}"
                rows.append((tconst, "movie", f"Movie {i}", f"Movie {i}", 0,
                             2000+i%20, None, 90+i, "Drama,Test", 7.0+i/100, 100+i))
            conn.executemany("INSERT INTO movies VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
            conn.commit(); conn.close()

            with MirrorServer(source, port=0, page_size=5, movie_limit=0, pool_size=8) as mirror:
                crawler = FocusedWebCrawler(
                    mirror.seed_url, mirror.allowed_netloc, output,
                    source_movie_count=23, expected_listing_pages=5, expected_total_pages=29,
                    max_depth=2, max_pages=29, workers=4, fetch_batch_size=8,
                    request_timeout=5, crawl_delay=0, reset=True, verbose_every=1000,
                )
                try:
                    result = crawler.crawl()
                finally:
                    crawler.close()

            self.assertEqual(result["pages_saved"], 29)
            self.assertEqual(result["movie_pages_saved"], 23)
            self.assertEqual(result["depth_counts"], {0: 1, 1: 5, 2: 23})
            passed, stats = validate_crawl(output, source, page_size=5, movie_limit=0, print_report=False)
            self.assertTrue(passed)
            self.assertEqual(stats["missing_movies"], 0)
            self.assertEqual(stats["metadata_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
