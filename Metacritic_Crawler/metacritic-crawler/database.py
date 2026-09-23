"""Task 8: pages/links theo đề; thêm events để ghi lỗi và kiểm tra kết quả."""
import sqlite3


def connect_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE, domain TEXT, title TEXT, content TEXT,
            depth INTEGER, status_code INTEGER, crawled_at TEXT,
            response_time REAL
        );
        CREATE TABLE links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT, target_url TEXT,
            UNIQUE(source_url, target_url)
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT, depth INTEGER, status_code INTEGER,
            kind TEXT, message TEXT, response_time REAL, crawled_at TEXT
        );
    """)
    return db


def save_page(db, record):
    db.execute("""INSERT INTO pages
        (url, domain, title, content, depth, status_code, crawled_at, response_time)
        VALUES (:url, :domain, :title, :content, :depth, :status_code, :crawled_at, :response_time)
    """, record)
    db.commit()


def save_link(db, source, target):
    db.execute("INSERT OR IGNORE INTO links(source_url, target_url) VALUES (?, ?)",
               (source, target))


def save_event(db, url, depth, status, kind, message, elapsed, timestamp):
    db.execute("""INSERT INTO events
        (url, depth, status_code, kind, message, response_time, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (url, depth, status, kind, message, elapsed, timestamp))
    db.commit()

