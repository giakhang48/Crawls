import argparse
import math
from pathlib import Path

import config
from downloader import download_official_datasets
from imdb_policy_check import check_imdb
from mirror_server import MirrorServer
from source_builder import build_source_db
from source_catalog import inspect_source, prepare_source
from validate import validate_crawl
from web_crawler import FocusedWebCrawler


def build_parser():
    p = argparse.ArgumentParser(description="SEG301 IMDb real web crawler using a local IMDb HTML mirror")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("prepare-source", help="Copy the old 757k imdb.db to data/imdb_source.db")
    sp.add_argument("--from-db", required=True, help="Path to the OLD official-dataset imdb.db")
    sp.add_argument("--to-db", default=str(config.SOURCE_DB))

    sp = sub.add_parser("build-source", help="Build imdb_source.db from official IMDb TSV datasets")
    sp.add_argument("--force-download", action="store_true")
    sp.add_argument("--source-db", default=str(config.SOURCE_DB))

    sub.add_parser("source-info", help="Show source movie count")
    sub.add_parser("imdb-check", help="Check direct IMDb robots policy; no bypass")

    for name, help_text, default_output, default_limit in [
        ("crawl-test", "Real HTTP crawl of a small deterministic subset", config.TEST_OUTPUT_DB, 1000),
        ("crawl-full", "Real HTTP crawl of ALL movies in the local mirror", config.OUTPUT_DB, 0),
    ]:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--source-db", default=str(config.SOURCE_DB))
        sp.add_argument("--output-db", default=str(default_output))
        sp.add_argument("--limit-movies", type=int, default=default_limit,
                        help="0 = all source movies")
        sp.add_argument("--page-size", type=int, default=config.MIRROR_PAGE_SIZE)
        sp.add_argument("--workers", type=int, default=config.WORKERS)
        sp.add_argument("--port", type=int, default=config.MIRROR_PORT)
        sp.add_argument("--max-depth", type=int, default=config.MAX_DEPTH)
        sp.add_argument("--max-pages", type=int, default=0,
                        help="0 = exact expected page count; nonzero demonstrates page-limit stopping")
        sp.add_argument("--reset", action="store_true")
        sp.add_argument("--verbose-every", type=int, default=10000)

    sp = sub.add_parser("validate", help="Validate crawler output against source catalog")
    sp.add_argument("--source-db", default=str(config.SOURCE_DB))
    sp.add_argument("--output-db", default=str(config.OUTPUT_DB))
    sp.add_argument("--limit-movies", type=int, default=0)
    sp.add_argument("--page-size", type=int, default=config.MIRROR_PAGE_SIZE)

    return p


def run_crawl(args):
    source_db = Path(args.source_db)
    output_db = Path(args.output_db)
    total_source = inspect_source(source_db)
    movie_count = min(total_source, args.limit_movies) if args.limit_movies else total_source
    listing_pages = math.ceil(movie_count / args.page_size) if movie_count else 0
    expected_total = 1 + listing_pages + movie_count
    max_pages = args.max_pages or expected_total

    print(f"Source DB               : {source_db}")
    print(f"Source movie count      : {total_source:,}")
    print(f"Mirror movie count      : {movie_count:,}")
    print(f"Mirror listing pages    : {listing_pages:,}")
    print(f"Expected crawl pages    : {expected_total:,}")
    print()

    with MirrorServer(
        source_db=source_db,
        host=config.MIRROR_HOST,
        port=args.port,
        page_size=args.page_size,
        movie_limit=args.limit_movies,
        pool_size=max(args.workers * 2, 8),
    ) as mirror:
        print(f"Local mirror online     : {mirror.seed_url}")
        crawler = FocusedWebCrawler(
            seed_url=mirror.seed_url,
            allowed_netloc=mirror.allowed_netloc,
            db_path=output_db,
            source_movie_count=movie_count,
            expected_listing_pages=listing_pages,
            expected_total_pages=expected_total,
            max_depth=args.max_depth,
            max_pages=max_pages,
            workers=args.workers,
            fetch_batch_size=config.FETCH_BATCH_SIZE,
            request_timeout=config.REQUEST_TIMEOUT,
            crawl_delay=config.CRAWL_DELAY,
            user_agent=config.USER_AGENT,
            request_retries=config.REQUEST_RETRIES,
            retry_backoff=config.RETRY_BACKOFF,
            reset=args.reset,
            verbose_every=args.verbose_every,
        )
        try:
            crawler.crawl()
        finally:
            crawler.close()

    # Only claim completeness when the caller did not intentionally cap max_pages
    # below the expected complete graph.
    if max_pages >= expected_total and args.max_depth >= 2:
        passed, _ = validate_crawl(output_db, source_db, args.page_size, args.limit_movies)
        if not passed:
            raise SystemExit(2)
    else:
        print("\nValidation of full completeness skipped because max-pages/max-depth intentionally limits the crawl.")
    print(f"\nDONE -> {output_db.resolve()}")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "prepare-source":
        count = prepare_source(args.from_db, args.to_db)
        print(f"Source catalog ready: {Path(args.to_db).resolve()}")
        print(f"Movies: {count:,}")
    elif args.command == "build-source":
        files = download_official_datasets(force=args.force_download)
        stats = build_source_db(files["title.basics"], files["title.ratings"], args.source_db, reset=True)
        print(stats)
        print(f"Source catalog ready: {Path(args.source_db).resolve()}")
    elif args.command == "source-info":
        count = inspect_source(config.SOURCE_DB)
        print(f"Source DB: {config.SOURCE_DB.resolve()}")
        print(f"Movies   : {count:,}")
    elif args.command == "imdb-check":
        check_imdb(config.USER_AGENT, config.REQUEST_TIMEOUT)
    elif args.command in {"crawl-test", "crawl-full"}:
        run_crawl(args)
    elif args.command == "validate":
        passed, _ = validate_crawl(args.output_db, args.source_db, args.page_size, args.limit_movies)
        if not passed:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
