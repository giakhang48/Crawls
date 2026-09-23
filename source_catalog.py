"""Prepare/inspect the IMDb source catalog used by the local HTTP mirror.

The source catalog is NOT the final crawler output. It is analogous to the
content store behind a website. The final data/imdb.db is populated only from
HTTP responses parsed by the crawler.
"""

from pathlib import Path
import sqlite3

REQUIRED_MOVIE_COLUMNS = {
    "tconst", "primary_title", "original_title", "start_year",
    "runtime_minutes", "genres", "average_rating", "num_votes",
}


def inspect_source(db_path):
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Source DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "movies" not in tables:
            raise ValueError("Source DB must contain a 'movies' table.")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(movies)")}
        missing = sorted(REQUIRED_MOVIE_COLUMNS - columns)
        if missing:
            raise ValueError(f"Source movies table is missing columns: {missing}")
        count = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        if count <= 0:
            raise ValueError("Source movies table is empty.")
        return count
    finally:
        conn.close()


def prepare_source(from_db, to_db):
    """SQLite backup-copy the old corpus DB to a safe source DB."""
    from_db = Path(from_db).resolve()
    to_db = Path(to_db).resolve()
    if from_db == to_db:
        raise ValueError("Input and destination source DB must be different files.")
    count = inspect_source(from_db)
    to_db.parent.mkdir(parents=True, exist_ok=True)
    if to_db.exists():
        to_db.unlink()
    src = sqlite3.connect(from_db)
    dst = sqlite3.connect(to_db)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    copied_count = inspect_source(to_db)
    if copied_count != count:
        raise RuntimeError(f"Backup row count mismatch: source={count}, copy={copied_count}")
    return copied_count
