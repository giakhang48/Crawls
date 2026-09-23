import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    source_domain TEXT NOT NULL DEFAULT 'imdb.com',
    canonical_url TEXT,
    page_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    depth INTEGER NOT NULL,
    status_code INTEGER,
    response_time REAL,
    crawled_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    is_valid INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    UNIQUE(source_url, target_url)
);

CREATE TABLE IF NOT EXISTS movies (
    tconst TEXT PRIMARY KEY,
    primary_title TEXT NOT NULL,
    original_title TEXT,
    start_year INTEGER,
    runtime_minutes INTEGER,
    genres TEXT,
    average_rating REAL,
    num_votes INTEGER,
    crawled_url TEXT NOT NULL,
    canonical_url TEXT
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    url TEXT,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS robots_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    robots_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT NOT NULL,
    seed_url TEXT NOT NULL,
    max_depth INTEGER NOT NULL,
    max_pages INTEGER NOT NULL,
    workers INTEGER NOT NULL,
    source_movie_count INTEGER NOT NULL,
    expected_listing_pages INTEGER NOT NULL,
    expected_total_pages INTEGER NOT NULL,
    pages_requested INTEGER DEFAULT 0,
    pages_saved INTEGER DEFAULT 0,
    movie_pages_saved INTEGER DEFAULT 0,
    links_saved INTEGER DEFAULT 0,
    unique_urls_discovered INTEGER DEFAULT 0,
    filtered_links INTEGER DEFAULT 0,
    skipped_urls INTEGER DEFAULT 0,
    duplicate_contents INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    stop_reason TEXT
);

CREATE TABLE IF NOT EXISTS validation_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    record_id TEXT,
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pages_type ON pages(page_type);
CREATE INDEX IF NOT EXISTS idx_pages_depth ON pages(depth);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status_code);
CREATE INDEX IF NOT EXISTS idx_pages_canonical ON pages(canonical_url);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);
CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(primary_title);
CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(start_year);

DROP VIEW IF EXISTS movie_documents;
CREATE VIEW movie_documents AS
SELECT p.id, p.url AS crawled_url, p.canonical_url, p.title, p.content,
       p.depth, p.status_code, p.crawled_at, p.content_hash,
       m.tconst, m.original_title, m.start_year, m.runtime_minutes,
       m.genres, m.average_rating, m.num_votes
FROM pages p
JOIN movies m ON m.crawled_url = p.url
WHERE p.page_type = 'movie';
"""


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(SCHEMA)
    return conn


def reset_database(db_path):
    path = Path(db_path)
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if candidate.exists():
            candidate.unlink()
