import argparse
from datetime import datetime
import config
from crawler import Crawler


def main():
    parser = argparse.ArgumentParser(description="SEG301 Metacritic Movie BFS Crawler")
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES)
    parser.add_argument("--max-depth", type=int, default=config.MAX_DEPTH)
    parser.add_argument("--max-requests", type=int, default=config.MAX_REQUESTS)
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_depth < 0 or args.max_requests < 1:
        parser.error("max-pages/max-requests must be positive; max-depth must be nonnegative")
    config.MAX_PAGES, config.MAX_DEPTH = args.max_pages, args.max_depth
    config.MAX_REQUESTS = args.max_requests
    output = config.DATA_DIR / datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    print("FOCUSED WEB CRAWLER |", config.TOPIC)
    print("Individual assignment: Metacritic only")
    print("Seed URLs:", *config.SEED_URLS, sep="\n  ")
    print(f"Max pages: {config.MAX_PAGES} | Max depth: {config.MAX_DEPTH}")
    print(f"Timeout: {config.REQUEST_TIMEOUT}s | Delay: {config.CRAWL_DELAY}s")
    Crawler(config, output).run()


if __name__ == "__main__":
    main()
