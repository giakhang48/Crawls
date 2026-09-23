import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                domain TEXT,
                title TEXT,
                content TEXT,
                depth INTEGER,
                status_code INTEGER,
                crawled_at TEXT,
                response_time REAL,
                book_title TEXT,
                price TEXT,
                rating TEXT,
                category TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                target_url TEXT,
                UNIQUE(source_url, target_url)
            )
        """)

        self.conn.commit()

    def save_page(self, data):
        self.conn.execute("""
            INSERT OR REPLACE INTO pages (
                url, domain, title, content, depth,
                status_code, crawled_at, response_time,
                book_title, price, rating, category
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["url"],
            data["domain"],
            data["title"],
            data["content"],
            data["depth"],
            data["status_code"],
            data["crawled_at"],
            data["response_time"],
            data["book_title"],
            data["price"],
            data["rating"],
            data["category"],
        ))
        self.conn.commit()

    def save_link(self, source_url, target_url):
        self.conn.execute("""
            INSERT OR IGNORE INTO links (source_url, target_url)
            VALUES (?, ?)
        """, (source_url, target_url))
        self.conn.commit()

    def close(self):
        self.conn.close()
