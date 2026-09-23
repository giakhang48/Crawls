from datetime import datetime, timezone
from pathlib import Path
import math
import sqlite3


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _record(conn, issue_type, message, record_id=None):
    conn.execute(
        "INSERT INTO validation_issues(checked_at,issue_type,record_id,message) VALUES (?,?,?,?)",
        (now_iso(), issue_type, record_id, message),
    )


def validate_crawl(output_db, source_db, page_size=5000, movie_limit=0, print_report=True):
    output_db = Path(output_db)
    source_db = Path(source_db)
    if not output_db.exists():
        raise FileNotFoundError(output_db)
    if not source_db.exists():
        raise FileNotFoundError(source_db)

    conn = sqlite3.connect(output_db)
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM validation_issues")
    conn.execute("ATTACH DATABASE ? AS src", (str(source_db),))

    source_total = conn.execute("SELECT COUNT(*) FROM src.movies").fetchone()[0]
    expected_movies = min(source_total, int(movie_limit)) if movie_limit else source_total
    expected_listing = math.ceil(expected_movies / page_size) if expected_movies else 0
    expected_total = 1 + expected_listing + expected_movies
    expected_links = expected_listing + expected_movies

    stats = {
        "source_total_movies": source_total,
        "expected_movies": expected_movies,
        "expected_listing_pages": expected_listing,
        "expected_total_pages": expected_total,
        "expected_links": expected_links,
        "pages": conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0],
        "movie_pages": conn.execute("SELECT COUNT(*) FROM pages WHERE page_type='movie'").fetchone()[0],
        "listing_pages": conn.execute("SELECT COUNT(*) FROM pages WHERE page_type='listing'").fetchone()[0],
        "root_pages": conn.execute("SELECT COUNT(*) FROM pages WHERE page_type='root'").fetchone()[0],
        "movies": conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0],
        "links": conn.execute("SELECT COUNT(*) FROM links").fetchone()[0],
        "http_200": conn.execute("SELECT COUNT(*) FROM pages WHERE status_code=200").fetchone()[0],
        "invalid_pages": conn.execute("SELECT COUNT(*) FROM pages WHERE is_valid=0 OR title='' OR content=''").fetchone()[0],
        "duplicate_urls": conn.execute("SELECT COUNT(*) FROM (SELECT url FROM pages GROUP BY url HAVING COUNT(*)>1)").fetchone()[0],
        "duplicate_hashes": conn.execute("SELECT COUNT(*) FROM (SELECT content_hash FROM pages GROUP BY content_hash HAVING COUNT(*)>1)").fetchone()[0],
        "bad_depth": conn.execute("""SELECT COUNT(*) FROM pages WHERE
            (page_type='root' AND depth<>0) OR
            (page_type='listing' AND depth<>1) OR
            (page_type='movie' AND depth<>2)""").fetchone()[0],
        "errors": conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0],
    }

    # Exact set comparison for movie IDs. For limited tests, compare with the
    # first N source tconst values because the mirror exposes that deterministic subset.
    conn.execute("DROP TABLE IF EXISTS temp.expected_ids")
    conn.execute("CREATE TEMP TABLE expected_ids(tconst TEXT PRIMARY KEY)")
    conn.execute(
        "INSERT INTO expected_ids SELECT tconst FROM src.movies ORDER BY tconst LIMIT ?",
        (expected_movies,),
    )
    stats["missing_movies"] = conn.execute(
        "SELECT COUNT(*) FROM expected_ids e LEFT JOIN movies m ON m.tconst=e.tconst WHERE m.tconst IS NULL"
    ).fetchone()[0]
    stats["unexpected_movies"] = conn.execute(
        "SELECT COUNT(*) FROM movies m LEFT JOIN expected_ids e ON e.tconst=m.tconst WHERE e.tconst IS NULL"
    ).fetchone()[0]

    # Compare fields that the crawler extracted from HTML against the source backend.
    stats["metadata_mismatches"] = conn.execute(
        """SELECT COUNT(*)
           FROM movies m JOIN src.movies s ON s.tconst=m.tconst
           WHERE COALESCE(m.primary_title,'') <> COALESCE(s.primary_title,'')
              OR COALESCE(m.original_title,'') <> COALESCE(s.original_title,'')
              OR COALESCE(m.start_year,-1) <> COALESCE(s.start_year,-1)
              OR COALESCE(m.runtime_minutes,-1) <> COALESCE(s.runtime_minutes,-1)
              OR COALESCE(m.genres,'') <> COALESCE(s.genres,'')
              OR COALESCE(m.average_rating,-1.0) <> COALESCE(s.average_rating,-1.0)
              OR COALESCE(m.num_votes,-1) <> COALESCE(s.num_votes,-1)"""
    ).fetchone()[0]

    checks = [
        (stats["pages"] == expected_total, "page_count", f"pages={stats['pages']:,}, expected={expected_total:,}"),
        (stats["movie_pages"] == expected_movies, "movie_page_count", f"movie_pages={stats['movie_pages']:,}, expected={expected_movies:,}"),
        (stats["listing_pages"] == expected_listing, "listing_count", f"listing_pages={stats['listing_pages']:,}, expected={expected_listing:,}"),
        (stats["root_pages"] == 1, "root_count", f"root_pages={stats['root_pages']:,}, expected=1"),
        (stats["movies"] == expected_movies, "movie_table_count", f"movies={stats['movies']:,}, expected={expected_movies:,}"),
        (stats["links"] == expected_links, "link_count", f"links={stats['links']:,}, expected={expected_links:,}"),
        (stats["http_200"] == expected_total, "http_status", f"HTTP200={stats['http_200']:,}, expected={expected_total:,}"),
        (stats["invalid_pages"] == 0, "invalid_page", f"invalid_pages={stats['invalid_pages']:,}"),
        (stats["duplicate_urls"] == 0, "duplicate_url", f"duplicate_urls={stats['duplicate_urls']:,}"),
        (stats["duplicate_hashes"] == 0, "duplicate_content", f"duplicate_hash_groups={stats['duplicate_hashes']:,}"),
        (stats["bad_depth"] == 0, "depth", f"bad_depth={stats['bad_depth']:,}"),
        (stats["missing_movies"] == 0, "missing_movie", f"missing_movies={stats['missing_movies']:,}"),
        (stats["unexpected_movies"] == 0, "unexpected_movie", f"unexpected_movies={stats['unexpected_movies']:,}"),
        (stats["metadata_mismatches"] == 0, "metadata_mismatch", f"metadata_mismatches={stats['metadata_mismatches']:,}"),
        (stats["errors"] == 0, "crawl_errors", f"errors={stats['errors']:,}"),
    ]

    for ok, issue_type, message in checks:
        if not ok:
            _record(conn, issue_type, message)
    conn.commit()
    passed = all(ok for ok, _, _ in checks)

    if print_report:
        print()
        print("=" * 78)
        print("IMDb LOCAL-MIRROR WEB CRAWL VALIDATION")
        print("=" * 78)
        print(f"Source movies available : {source_total:,}")
        print(f"Movies in this crawl    : {expected_movies:,}")
        print(f"Expected total pages    : {expected_total:,}")
        print(f"Pages actually crawled  : {stats['pages']:,}")
        print(f"Movie pages             : {stats['movie_pages']:,}")
        print(f"Listing pages           : {stats['listing_pages']:,}")
        print(f"Links                   : {stats['links']:,}")
        print(f"HTTP 200 pages          : {stats['http_200']:,}")
        print(f"Missing movies          : {stats['missing_movies']:,}")
        print(f"Unexpected movies       : {stats['unexpected_movies']:,}")
        print(f"Metadata mismatches     : {stats['metadata_mismatches']:,}")
        print(f"Invalid pages           : {stats['invalid_pages']:,}")
        print(f"Duplicate URL groups    : {stats['duplicate_urls']:,}")
        print(f"Duplicate content groups: {stats['duplicate_hashes']:,}")
        print(f"Bad crawl depths        : {stats['bad_depth']:,}")
        print(f"Crawl errors            : {stats['errors']:,}")
        print("-" * 78)
        print("RESULT: PASS" if passed else "RESULT: FAIL - inspect validation_issues")
        print("=" * 78)

    conn.close()
    return passed, stats
