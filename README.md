# SEG301 – Wikipedia Movies Focused Web Crawler

## What this project does

This is a **real public-web crawler** for English Wikipedia movie pages.

It starts only from:

`https://en.wikipedia.org/wiki/Lists_of_films`

Then it discovers:

1. alphabetic movie-list pages (`List_of_films:_A` … `Z`, `numbers`);
2. movie article candidates linked from those pages;
3. downloads each discovered page using **Requests**;
4. parses HTML using **BeautifulSoup**;
5. stores documents and hyperlinks in **SQLite**.

The crawler does **not** use a pre-downloaded movie dataset or local mirror.

## Focused BFS scope

```
Depth 0
Lists_of_films
    |
    v
Depth 1
List_of_films:_A ... Z + numbers
    |
    v
Depth 2
Individual movie article candidates
```

Movie pages are terminal nodes in this focused crawler; links from movie pages are not followed.

This prevents the crawler from drifting into actors, directors, countries, years, references, etc.

## Why Wikipedia?

Wikipedia's current robots.txt explicitly states that friendly, low-speed bots are welcome on article pages, while dynamic `/w/`, API and special pages are restricted.

This crawler:

- reads robots.txt before crawling;
- checks `can_fetch()` before every request;
- stays inside `en.wikipedia.org/wiki/`;
- avoids Wikipedia special namespaces;
- uses a transparent User-Agent;
- uses a polite crawl delay (default 1 second).

## Project structure

```
Assignment1/
├── main.py
├── config.py
├── crawler.py
├── url_frontier.py
├── parser.py
├── duplicate.py
├── database.py
├── validate.py
├── requirements.txt
├── README.md
├── .gitignore
└── data/
    └── wikipedia_movies.db   # generated after crawling
```

## Setup

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 1. Check robots.txt

```powershell
python main.py robots-check
```

Expected for the seed: `ALLOW`.

## 2. Test first

```powershell
python main.py crawl-test --reset
```

Default test cap: 100 saved pages.

## 3. Full crawl

```powershell
python main.py crawl-full --reset
```

Default configuration:

- max depth: 2
- max pages: 100,000
- delay: 2 seconds (plus Retry-After / exponential backoff on HTTP 429/503)

To use another cap:

```powershell
python main.py crawl-full --reset --max-pages 20000
```

## Resume after interruption

If VS Code or the terminal closes, **do not use `--reset`**:

```powershell
python main.py crawl-full
```

Existing pages in SQLite are marked visited and pending links are reconstructed from the saved link graph.

## Validate result

```powershell
python main.py validate
```

## SQLite output

### `pages`

Main Search Engine document collection:

- URL
- domain
- page type
- title
- visible textual content
- BFS depth
- HTTP status
- response time
- crawl timestamp
- SHA-256 content hash
- validation flags

### `links`

Actual hyperlinks discovered from HTML:

- `source_url`
- `target_url`

### `movies`

Best-effort film metadata parsed from Wikipedia infoboxes:

- title
- director
- release date
- running time
- country
- language
- probable-film flag

### `errors`, `robots_checks`, `crawl_runs`

Audit / analysis tables.

## Important scope note

The crawler can prove completeness only **within its defined frontier and stopping conditions**.

If it stops because `URL Frontier is empty`, then every URL discovered in this focused A-Z crawl scope has been processed.

If it stops because `MAX_PAGES reached`, the crawl is intentionally incomplete and should be resumed/increased before claiming full coverage.


## V2 fixes for live Wikipedia

- Uses a descriptive bot User-Agent with the project URL as contact information.
- Respects HTTP `Retry-After` on 429 / 503 responses.
- Uses exponential backoff when `Retry-After` is absent.
- Recognizes Wikipedia's grouped film-index pages such as:
  - `List_of_films:_J–K`
  - `List_of_films:_N–O`
  - `List_of_films:_Q–R`
  - `List_of_films:_U–V–W`
  - `List_of_films:_X–Y–Z`

The live Wikipedia index is not simply 26 independent A-Z pages, so this matters for completeness.
