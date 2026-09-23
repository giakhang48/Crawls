import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    domain TEXT,
    title TEXT,
    content TEXT,
    depth INTEGER,
    status_code INTEGER,
    crawled_at TEXT,
    film_name TEXT,
    release_year TEXT,
    director TEXT,
    rating_value REAL,
    rating_count INTEGER
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT,
    target_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain);
CREATE INDEX IF NOT EXISTS idx_pages_depth ON pages(depth);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
"""


class CrawlerDB:
    def __init__(self, path: str):
        db_path = Path(path)

        # Tự tạo thư mục data nếu chưa tồn tại.
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save_page(self, page: dict):
        self.conn.execute(
            """
            INSERT OR IGNORE INTO pages
            (url, domain, title, content, depth, status_code, crawled_at,
             film_name, release_year, director, rating_value, rating_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                page["url"],
                page["domain"],
                page["title"],
                page["content"],
                page["depth"],
                page["status_code"],
                page["crawled_at"],
                page.get("film_name"),
                page.get("release_year"),
                page.get("director"),
                page.get("rating_value"),
                page.get("rating_count"),
            ),
        )
        self.conn.commit()

    def save_link(self, source_url: str, target_url: str):
        self.conn.execute(
            "INSERT INTO links (source_url, target_url) VALUES (?, ?)",
            (source_url, target_url),
        )

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
