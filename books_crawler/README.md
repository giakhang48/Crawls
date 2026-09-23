# Books to Scrape - Simple Web Crawler

A small educational web crawler for `https://books.toscrape.com/`.

## Features

- Breadth-First Search (BFS)
- URL frontier using `collections.deque`
- Duplicate URL detection
- Relative URL normalization
- Domain filtering
- HTTP status handling
- Timeout/request error handling
- HTML parsing with BeautifulSoup
- SQLite storage
- Crawl depth control
- Crawl statistics
- Book-specific extraction:
  - Book title
  - Price
  - Rating
  - Category

## Project structure

```text
books_crawler/
├── main.py
├── crawler.py
├── parser.py
├── url_frontier.py
├── database.py
├── config.py
├── requirements.txt
├── README.md
└── data/
    └── crawler.db
```

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The SQLite database will be created at:

```text
data/crawler.db
```

## Configuration

Edit `config.py`:

```python
MAX_PAGES = 50
MAX_DEPTH = 3
REQUEST_TIMEOUT = 10
CRAWL_DELAY = 1.0
```

## Database

### pages

Stores crawled page information:

- URL
- domain
- title
- content
- depth
- HTTP status
- crawl timestamp
- response time
- book title
- price
- rating
- category

### links

Stores relationships between source pages and discovered target URLs.

## Notes

This is an educational crawler. It intentionally keeps the implementation simple so that the crawling flow is easy to understand and modify.
