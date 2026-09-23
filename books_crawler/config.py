# Crawler configuration

BASE_URL = "https://books.toscrape.com/"
SEED_URLS = [BASE_URL]

ALLOWED_DOMAINS = {"books.toscrape.com"}

MAX_PAGES = 50
MAX_DEPTH = 3
REQUEST_TIMEOUT = 10
CRAWL_DELAY = 1.0

USER_AGENT = "SimpleBooksCrawler/1.0"
DB_PATH = "data/crawler.db"
