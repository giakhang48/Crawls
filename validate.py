import sqlite3
from collections import Counter


def validate(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    counts = {}
    counts["pages"] = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    counts["root"] = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE page_type='root'"
    ).fetchone()[0]
    counts["lists"] = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE page_type='list'"
    ).fetchone()[0]
    counts["movies"] = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE page_type='movie'"
    ).fetchone()[0]
    counts["probable_films"] = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE page_type='movie' AND probable_film=1"
    ).fetchone()[0]
    counts["links"] = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
    counts["invalid"] = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE is_valid=0"
    ).fetchone()[0]
    counts["non_200"] = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE status_code<>200 OR status_code IS NULL"
    ).fetchone()[0]
    counts["duplicate_urls"] = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT url FROM pages GROUP BY url HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    counts["duplicate_hashes"] = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT content_hash FROM pages
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    unresolved_errors = conn.execute(
        """
        SELECT COUNT(*)
        FROM errors e
        LEFT JOIN pages p ON p.url=e.url
        WHERE p.url IS NULL
        """
    ).fetchone()[0]

    depth_counts = {
        row["depth"]: row["n"]
        for row in conn.execute(
            "SELECT depth,COUNT(*) n FROM pages GROUP BY depth ORDER BY depth"
        )
    }

    latest = conn.execute(
        "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()

    print("=" * 76)
    print("WIKIPEDIA MOVIES CRAWL VALIDATION")
    print("=" * 76)
    print(f"Pages                    : {counts['pages']:,}")
    print(f"Root pages               : {counts['root']:,}")
    print(f"List pages               : {counts['lists']:,}")
    print(f"Movie candidate pages    : {counts['movies']:,}")
    print(f"Probable film articles   : {counts['probable_films']:,}")
    print(f"Links                    : {counts['links']:,}")
    print(f"Invalid pages            : {counts['invalid']:,}")
    print(f"Non-HTTP-200 saved pages : {counts['non_200']:,}")
    print(f"Duplicate URL groups     : {counts['duplicate_urls']:,}")
    print(f"Duplicate content groups : {counts['duplicate_hashes']:,}")
    print(f"Unresolved crawl errors  : {unresolved_errors:,}")
    for depth, n in depth_counts.items():
        print(f"Depth {depth:<2}                 : {n:,}")

    if latest:
        print("-" * 76)
        print(f"Latest stop reason       : {latest['stop_reason']}")

    hard_issues = (
        counts["pages"] == 0
        or counts["root"] != 1
        or counts["lists"] == 0
        or counts["movies"] == 0
        or counts["invalid"] > 0
        or counts["non_200"] > 0
        or counts["duplicate_urls"] > 0
        or counts["duplicate_hashes"] > 0
        or unresolved_errors > 0
    )

    print("-" * 76)
    if hard_issues:
        print("RESULT: CHECK REQUIRED")
    else:
        print("RESULT: PASS")
    print("=" * 76)

    conn.close()
    return not hard_issues
