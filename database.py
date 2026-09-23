import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    page_type TEXT NOT NULL,
    title TEXT,
    content TEXT,
    depth INTEGER NOT NULL,
    status_code INTEGER,
    response_time REAL,
    crawled_at TEXT NOT NULL,
    content_hash TEXT,
    is_valid INTEGER NOT NULL DEFAULT 1,
    probable_film INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    UNIQUE(source_url, target_url)
);

CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url TEXT UNIQUE NOT NULL,
    title TEXT,
    directed_by TEXT,
    release_date TEXT,
    running_time TEXT,
    country TEXT,
    language TEXT,
    probable_film INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    depth INTEGER,
    error_type TEXT,
    message TEXT,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS robots_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    seed_url TEXT NOT NULL,
    max_depth INTEGER NOT NULL,
    max_pages INTEGER NOT NULL,
    pages_saved INTEGER DEFAULT 0,
    movies_saved INTEGER DEFAULT 0,
    links_saved INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    stop_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_pages_type ON pages(page_type);
CREATE INDEX IF NOT EXISTS idx_pages_depth ON pages(depth);
CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);
"""


def connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def reset_database(db_path: Path):
    if db_path.exists():
        db_path.unlink()
