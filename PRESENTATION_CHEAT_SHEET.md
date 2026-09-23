# 60-second code walkthrough

> Em dùng Focused Web Crawler theo BFS. Seed duy nhất là `Lists_of_films` trên Wikipedia. URL Frontier dùng `deque`; crawler tải từng URL bằng Requests, parse HTML bằng BeautifulSoup, lấy title/content và `<a href>`, filter để chỉ giữ Wikipedia article URLs trong scope Movies rồi add lại vào Frontier. `visited/queued` tránh URL trùng, SHA-256 phát hiện exact duplicate content, có MAX_DEPTH/MAX_PAGES, robots.txt check và crawl delay. Kết quả lưu vào SQLite `wikipedia_movies.db`.

## Pipeline

Seed URL → URL Frontier (BFS) → robots check → Requests → HTML → BeautifulSoup → extract data + links → normalize/filter → Frontier → SQLite → validation

## Why Wikipedia?

IMDb blocks generic crawlers. Wikipedia's robots.txt allows friendly low-speed bots on normal article pages, so this backup domain lets the assignment run on a real public website without bypassing restrictions.

## What each file does

- `main.py`: commands / entry point
- `url_frontier.py`: BFS queue, queued, visited
- `crawler.py`: request loop, robots, depth, page limit, storage
- `parser.py`: BeautifulSoup, content extraction, hyperlinks, focus filtering
- `duplicate.py`: SHA-256 exact duplicate
- `database.py`: SQLite schema
- `validate.py`: quality / completion checks

## Likely Q&A

**What is a crawler?**  
A program that starts from seed URLs, downloads pages, extracts data and new links, then follows valid links automatically.

**Why BFS?**  
It explores the site level by level around the seed and makes crawl depth easy to control.

**Why `queued` and `visited`?**  
`queued` prevents duplicate URLs waiting in the frontier; `visited` prevents re-requesting pages already crawled.

**Requests vs BeautifulSoup?**  
Requests downloads HTTP pages; BeautifulSoup parses the returned HTML.

**Why SHA-256 if URL dedup already exists?**  
Different URLs can still return identical content. SHA-256 detects exact-content duplicates.

**How is this focused on movies?**  
Root → A-Z film lists → film article candidates. Movie-page links are terminal, so the crawler does not drift into actor/director/reference pages.

**How do you know crawl is complete?**  
If Frontier becomes empty before MAX_PAGES, all URLs discovered within the defined focused scope were processed. If MAX_PAGES is hit, it is not complete.

**Is this public-web crawling?**  
Yes. HTTP requests go directly to `en.wikipedia.org`; there is no local mirror or prebuilt movie database.
