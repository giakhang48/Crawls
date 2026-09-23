# Rubric defense guide

## One-sentence method

> I use a focused BFS Web Crawler on a local HTTP mirror of the assigned IMDb movie corpus. The crawler uses Requests + BeautifulSoup, extracts and filters real hyperlinks, records true depth/status/timestamps in SQLite, and validates the crawled movie IDs and parsed metadata against the source catalog.

## Why a local mirror?

Direct IMDb generic crawling is blocked by the current IMDb robots policy. The assignment requires respecting robots.txt. The local mirror lets the crawler mechanism be executed exactly as required without pretending that external IMDb pages were scraped.

## What makes this a REAL crawler?

- Seed is an HTTP URL.
- URL Frontier is a deque queue.
- Traversal is BFS.
- Every final document is obtained through `requests.get()`.
- HTML is parsed by BeautifulSoup.
- Movie metadata is extracted from the HTML returned by the server, not copied directly into the final DB.
- Links in `links` are `<a href>` values extracted from crawled HTML.
- `depth` is the real discovery depth.
- `status_code` is the real HTTP response code.
- `crawled_at` is the real crawl timestamp.
- SHA-256 detects exact duplicate HTML.
- Crawl stops when the frontier is empty, MAX_PAGES is reached, or the configured depth prevents further enqueueing.

## Why source DB and output DB must be different

`imdb_source.db` is the backend data used to render the website, analogous to a website's server-side database. `imdb.db` is the crawler result. The crawler has no SQL access to `imdb_source.db`; only `mirror_server.py` does. The crawler sees only HTTP HTML.

## Completeness proof

With source count N and page size K:

- listing pages = ceil(N/K)
- expected crawl pages = 1 + listing_pages + N
- expected HTML links = listing_pages + N

Validation then checks:

1. every expected movie tconst exists in crawler output,
2. no unexpected tconst exists,
3. fields parsed from HTML match the source backend,
4. root/listing/movie depths are exactly 0/1/2,
5. every crawled page is HTTP 200,
6. no empty title/content, duplicate URL/content or request error exists.

## Important wording

Do say: **“I crawled a local IMDb HTML mirror generated from IMDb official movie records.”**

Do not say: **“I crawled 757k pages directly from imdb.com.”**
