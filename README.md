# SEG301 Focused Web Crawler — Letterboxd

## 1. Selected Topic

**Movies & Entertainment**

Current test domain:

- Letterboxd — `https://letterboxd.com/`

> Assignment note: the specification asks for **at least 2 domains** from the selected topic.
> This project is intentionally configured for Letterboxd only because this is the
> domain requested for the current test. A second permitted domain must be added before
> claiming full compliance with that particular assignment requirement.

## 2. Seed URLs

```text
https://letterboxd.com/films/popular/
```

## 3. Crawling Configuration

Default values:

```text
MAX_PAGES       = 20
MAX_DEPTH       = 2
REQUEST_TIMEOUT = 10 seconds
CRAWL_DELAY     = 3 seconds
```

All configuration is located in `config.py`.

## 4. Crawling Strategy

The crawler uses **Breadth-First Search (BFS)**.

`URLFrontier` is implemented with Python `collections.deque`.

Flow:

```text
Seed URL
   ↓
URL Frontier (FIFO)
   ↓
Check depth / duplicate / robots.txt
   ↓
HTTP request
   ↓
BeautifulSoup
   ├── Extract page info + film metadata (JSON-LD)
   │        ↓
   │      SQLite
   │
   └── Extract hyperlinks
            ↓
       Normalize + filter (domain, extension, focused path)
            ↓
       URL Frontier
```

Each frontier item is stored as:

```python
(url, depth)
```

## 5. URL Filtering Rules

The crawler:

- accepts only `http://` or `https://`;
- restricts crawling to configured allowed domains (`letterboxd.com`, `www.letterboxd.com`);
- **focused crawling**: only follows links under `ALLOWED_PATH_PREFIXES` in `config.py`
  (by default `/film/` and `/films/popular/`), so the crawler stays on movie pages
  instead of drifting into user profiles, diaries, or reviews;
- explicitly blocks paths in `BLOCKED_PATH_PREFIXES` (search, settings, login, internal
  ajax/api endpoints) regardless of what robots.txt says;
- converts relative links to absolute links using `urljoin`;
- removes URL fragments;
- ignores `mailto:`, `javascript:`, `tel:` and `data:` links;
- ignores common non-HTML files such as images, CSS, JavaScript, ZIP and PDF;
- avoids duplicate crawling using `visited`;
- avoids duplicate queue entries;
- checks `robots.txt` before requesting a page (this is the authoritative check,
  independent of the two path lists above).

## 6. Information Extracted

For each successful HTML page:

- URL, domain, page title, text content, crawl depth, HTTP status code, crawl timestamp
- When the page is a film page and exposes `schema.org/Movie` JSON-LD data:
  film name, release year, director(s), aggregate rating value and rating count

The crawler intentionally does **not** perform tokenization, stopword removal,
stemming, lemmatization or TF-IDF because those are outside this assignment.

## 7. Database Design

SQLite database:

```text
data/crawler.db
```

### `pages`

| Column | Meaning |
|---|---|
| id | Primary key |
| url | Page URL, unique |
| domain | Website domain |
| title | Page title |
| content | Extracted text |
| depth | Crawl depth |
| status_code | HTTP status |
| crawled_at | Crawl timestamp |
| film_name | Movie title (from JSON-LD, if present) |
| release_year | Release year (from JSON-LD, if present) |
| director | Director name(s) (from JSON-LD, if present) |
| rating_value | Aggregate rating value (from JSON-LD, if present) |
| rating_count | Aggregate rating count (from JSON-LD, if present) |

### `links`

| Column | Meaning |
|---|---|
| id | Primary key |
| source_url | Page containing hyperlink |
| target_url | Hyperlink target |

## 8. robots.txt and Website Policy

The crawler is deliberately designed to honor `robots.txt`. If `robots.txt`
cannot be retrieved, the crawler skips the domain for safety rather than assuming
permission.

**Important — verify before running:**

- Open `https://letterboxd.com/robots.txt` yourself and check the current rules.
  Community projects that work with Letterboxd have noted that its robots.txt does
  not allow crawling filtered/sorted list URLs (e.g. `/films/popular/genre/...`,
  `/films/by/...`); this project's `ALLOWED_PATH_PREFIXES` avoids those by only
  targeting `/film/` and the base `/films/popular/` page, but you should confirm
  this still matches the live robots.txt before running.
- Check Letterboxd's current Terms of Use regarding automated access/scraping.
  Website policies can change over time — always check the live terms before
  running this against the real site, and prefer running it against a domain
  you have explicit permission to crawl if this is more than a local assignment test.

Regardless of what is written here, the crawler's `RobotFileParser`-based check in
`crawler.py` is what actually enforces access at runtime — it fetches the live
`robots.txt` on each run.

**Known limitation:** even when `robots.txt` explicitly allows a path, Letterboxd's
edge/WAF layer may return `HTTP 403` on the very first request (observed with the
default `USER_AGENT`). This is independent of the robots.txt check — it happens
after `allowed_by_robots()` already returned `True`, at the actual `session.get()`
call — and shows up in the run summary as `Failed Requests` / `HTTP 403`, not as a
`Skipped URL`. This is not a crawler bug; it reflects the target site's own
bot-protection and should be reported as such rather than worked around by
spoofing a browser User-Agent.

## 9. Run

```bash
cd letterboxd_crawler
python -m pip install -r requirements.txt
python main.py
```

Expected console structure:

```text
============================================================
CRAWLER CONFIGURATION
============================================================
...

[Crawl #001]
Depth : 0
URL   : ...
Status: ...
Time  : ...
Title : ...
Film  : ... (if a film page)
Links : ...

============================================================
CRAWLING SUMMARY
============================================================
Pages Crawled          : ...
Unique URLs Discovered : ...
Skipped URLs           : ...
Failed Requests        : ...
Depth 0                : ...
HTTP 200               : ...
============================================================
```

Statistics are calculated automatically from the crawler run; they are not hard-coded.

## 10. Project Structure

```text
letterboxd_crawler/
├── main.py
├── crawler.py
├── url_frontier.py
├── parser.py
├── database.py
├── config.py
├── requirements.txt
├── README.md
├── RUN_CRAWLER.bat
├── .gitignore
└── data/
    └── crawler.db   # created automatically when the program runs
```
