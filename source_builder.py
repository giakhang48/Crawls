"""Build data/imdb_source.db from official IMDb TSVs.

This is source preparation only. It does NOT write the final crawler pages.
The final data/imdb.db is produced by HTTP crawling the local mirror.
"""

import csv
import gzip
import sqlite3
from pathlib import Path

import config

SOURCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS movies (
    tconst TEXT PRIMARY KEY,
    title_type TEXT NOT NULL,
    primary_title TEXT NOT NULL,
    original_title TEXT,
    is_adult INTEGER,
    start_year INTEGER,
    end_year INTEGER,
    runtime_minutes INTEGER,
    genres TEXT,
    average_rating REAL,
    num_votes INTEGER
);
CREATE INDEX IF NOT EXISTS idx_source_title ON movies(primary_title);
CREATE INDEX IF NOT EXISTS idx_source_year ON movies(start_year);
"""


def _null(value):
    return None if value in (None, "", "\\N") else value


def _int(value):
    value = _null(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _float(value):
    value = _null(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def build_source_db(basics_path, ratings_path, output_db=config.SOURCE_DB, reset=True):
    output_db = Path(output_db)
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if reset and output_db.exists():
        output_db.unlink()

    conn = sqlite3.connect(output_db)
    conn.executescript(SOURCE_SCHEMA)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    insert_sql = """INSERT OR REPLACE INTO movies
        (tconst,title_type,primary_title,original_title,is_adult,start_year,end_year,runtime_minutes,genres)
        VALUES (?,?,?,?,?,?,?,?,?)"""
    batch = []
    scanned = movies = 0
    with gzip.open(basics_path, "rt", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            scanned += 1
            if row.get("titleType") != "movie":
                continue
            tconst = _null(row.get("tconst"))
            title = _null(row.get("primaryTitle"))
            if not tconst or not title:
                continue
            batch.append((
                tconst, "movie", title, _null(row.get("originalTitle")),
                _int(row.get("isAdult")), _int(row.get("startYear")),
                _int(row.get("endYear")), _int(row.get("runtimeMinutes")),
                _null(row.get("genres")),
            ))
            if len(batch) >= config.IMPORT_BATCH_SIZE:
                conn.executemany(insert_sql, batch)
                movies += len(batch)
                batch.clear()
                conn.commit()
                print(f"\r[source basics] movies: {movies:,}", end="")
    if batch:
        conn.executemany(insert_sql, batch)
        movies += len(batch)
        conn.commit()
    print(f"\r[source basics] movies: {movies:,}")

    update_sql = "UPDATE movies SET average_rating=?, num_votes=? WHERE tconst=?"
    batch = []
    matched = 0
    with gzip.open(ratings_path, "rt", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            batch.append((_float(row.get("averageRating")), _int(row.get("numVotes")), row.get("tconst")))
            if len(batch) >= config.IMPORT_BATCH_SIZE:
                before = conn.total_changes
                conn.executemany(update_sql, batch)
                matched += conn.total_changes - before
                batch.clear()
                conn.commit()
                print(f"\r[source ratings] matched: {matched:,}", end="")
    if batch:
        before = conn.total_changes
        conn.executemany(update_sql, batch)
        matched += conn.total_changes - before
        conn.commit()
    print(f"\r[source ratings] matched: {matched:,}")
    conn.close()
    return {"source_rows_scanned": scanned, "movies": movies, "ratings_matched": matched}
