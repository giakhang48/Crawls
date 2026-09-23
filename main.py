import argparse

import config
from crawler import WikipediaMovieCrawler
from database import reset_database
from validate import validate


def run_crawl(args, test_mode=False):
    db_path = config.DB_PATH

    if args.reset:
        reset_database(db_path)

    max_pages = args.max_pages
    if max_pages is None:
        max_pages = 100 if test_mode else config.MAX_PAGES

    crawler = WikipediaMovieCrawler(
        db_path=db_path,
        max_depth=args.max_depth,
        max_pages=max_pages,
        crawl_delay=args.delay,
    )

    try:
        crawler.crawl()
    finally:
        crawler.close()

    validate(db_path)


def robots_check():
    crawler = WikipediaMovieCrawler(
        db_path=config.DB_PATH,
        max_depth=0,
        max_pages=1,
    )
    try:
        allowed = crawler.load_robots()
        print()
        print("Wikipedia seed crawl policy:")
        print("ALLOW" if allowed else "BLOCK")
    finally:
        crawler.close()


def main():
    parser = argparse.ArgumentParser(
        description="SEG301 Wikipedia Movies Focused Web Crawler"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in [
        ("crawl-test", "Crawl a small sample (default 100 saved pages)."),
        ("crawl-full", "Run the focused crawl with the configured page cap."),
    ]:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing wikipedia_movies.db before crawling.",
        )
        sp.add_argument(
            "--max-pages",
            type=int,
            default=None,
            help="Override page limit.",
        )
        sp.add_argument(
            "--max-depth",
            type=int,
            default=config.MAX_DEPTH,
        )
        sp.add_argument(
            "--delay",
            type=float,
            default=config.CRAWL_DELAY,
            help="Delay between requests. Keep polite on public Wikipedia.",
        )

    sub.add_parser("robots-check", help="Check Wikipedia robots.txt for the seed.")
    sub.add_parser("validate", help="Validate the existing crawl database.")

    args = parser.parse_args()

    if args.command == "crawl-test":
        run_crawl(args, test_mode=True)
    elif args.command == "crawl-full":
        run_crawl(args, test_mode=False)
    elif args.command == "robots-check":
        robots_check()
    elif args.command == "validate":
        validate(config.DB_PATH)


if __name__ == "__main__":
    main()
