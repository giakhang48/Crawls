from crawler import BooksCrawler
from config import DB_PATH


def main():
    crawler = BooksCrawler(DB_PATH)

    try:
        crawler.crawl()
    finally:
        crawler.close()


if __name__ == "__main__":
    main()
