"""Dynamic local IMDb HTML mirror served over real HTTP.

The source SQLite DB behaves like the website's backend. The crawler NEVER
reads this DB. It only sees HTTP-delivered HTML pages and hyperlinks.
"""

from __future__ import annotations

from contextlib import contextmanager
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
import math
import sqlite3
import threading
import socket
from urllib.parse import urlparse


class ConnectionPool:
    def __init__(self, db_path, size=24):
        self.db_path = Path(db_path).resolve()
        self.pool = Queue(maxsize=size)
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        for _ in range(size):
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.pool.put(conn)

    @contextmanager
    def connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)

    def close(self):
        while not self.pool.empty():
            self.pool.get_nowait().close()


class MirrorData:
    def __init__(self, source_db, page_size=5000, movie_limit=0, pool_size=24):
        self.source_db = Path(source_db)
        self.page_size = int(page_size)
        self.pool = ConnectionPool(source_db, size=pool_size)
        with self.pool.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        self.total_source_movies = total
        self.movie_count = min(total, int(movie_limit)) if movie_limit else total
        self.listing_pages = math.ceil(self.movie_count / self.page_size) if self.movie_count else 0
        # Precompute the first tconst for each listing page in ONE sequential indexed scan.
        # This avoids running many large LIMIT/OFFSET queries concurrently on Windows,
        # which can make listing requests exceed the client timeout on a 757k-row corpus.
        self.page_starts = []
        if self.movie_count:
            with self.pool.connection() as conn:
                cur = conn.execute("SELECT tconst FROM movies ORDER BY tconst")
                for idx, row in enumerate(cur):
                    if idx >= self.movie_count:
                        break
                    if idx % self.page_size == 0:
                        self.page_starts.append(row[0])

    def listing_rows(self, page_number):
        if page_number < 1 or page_number > self.listing_pages:
            return []
        start_key = self.page_starts[page_number - 1]
        offset = (page_number - 1) * self.page_size
        remaining = self.movie_count - offset
        limit = min(self.page_size, remaining)
        with self.pool.connection() as conn:
            return conn.execute(
                """SELECT tconst, primary_title, start_year
                   FROM movies WHERE tconst >= ? ORDER BY tconst LIMIT ?""",
                (start_key, limit),
            ).fetchall()

    def movie(self, tconst):
        with self.pool.connection() as conn:
            return conn.execute(
                """SELECT tconst, primary_title, original_title, start_year,
                          runtime_minutes, genres, average_rating, num_votes
                   FROM movies WHERE tconst=?""",
                (tconst,),
            ).fetchone()

    def close(self):
        self.pool.close()


def _value(value):
    return "" if value is None else str(value)


def _movie_html(row):
    title = escape(_value(row["primary_title"]))
    original = escape(_value(row["original_title"]))
    year = escape(_value(row["start_year"]))
    runtime = escape(_value(row["runtime_minutes"]))
    genres = escape(_value(row["genres"]))
    rating = escape(_value(row["average_rating"]))
    votes = escape(_value(row["num_votes"]))
    tconst = escape(_value(row["tconst"]))
    canonical = f"https://www.imdb.com/title/{tconst}/"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<link rel="canonical" href="{canonical}">
</head><body>
<main data-page-type="movie" data-tconst="{tconst}">
<h1 data-field="primary_title">{title}</h1>
<p>Original title: <span data-field="original_title">{original}</span></p>
<p>Year: <span data-field="start_year">{year}</span></p>
<p>Runtime: <span data-field="runtime_minutes">{runtime}</span> minutes</p>
<p>Genres: <span data-field="genres">{genres}</span></p>
<p>IMDb rating: <span data-field="average_rating">{rating}</span></p>
<p>Votes: <span data-field="num_votes">{votes}</span></p>
<p>IMDb identifier: <span data-field="tconst">{tconst}</span></p>
</main></body></html>"""


def create_handler(data: MirrorData):
    class MirrorHandler(BaseHTTPRequestHandler):
        server_version = "SEG301IMDbMirror/1.0"
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            # Avoid Windows delayed-ACK/Nagle latency for thousands of tiny
            # localhost HTTP responses. This improves crawl throughput greatly.
            try:
                self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass

        def log_message(self, fmt, *args):
            # Avoid printing ~757k server log lines. Crawler prints its own progress.
            return

        def _send(self, status, body, content_type="text/html; charset=utf-8"):
            encoded = body.encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(encoded)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # The HTTP client may close a socket after a timeout/retry.
                # This is a transport event, not a mirror data error; the crawler
                # retries the request and validates completeness at the end.
                self.close_connection = True
                return
            except OSError as exc:
                # Windows: 10053/10054 = connection aborted/reset by peer.
                if getattr(exc, "winerror", None) in {10053, 10054}:
                    self.close_connection = True
                    return
                raise

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/robots.txt":
                self._send(200, "User-agent: *\nAllow: /\n", "text/plain; charset=utf-8")
                return

            if path in {"/", "/movies", "/movies/"}:
                links = "\n".join(
                    f'<li><a href="/movies/page/{i}/">Movie index page {i}</a></li>'
                    for i in range(1, data.listing_pages + 1)
                )
                html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>IMDb Movies Local Mirror</title></head><body>
<main data-page-type="root">
<h1>IMDb Movies Local Mirror</h1>
<p>Total movies: {data.movie_count}</p>
<p>Listing pages: {data.listing_pages}</p>
<ul>{links}</ul>
</main></body></html>"""
                self._send(200, html)
                return

            if path.startswith("/movies/page/"):
                try:
                    page_number = int(path.rstrip("/").split("/")[-1])
                except ValueError:
                    self._send(404, "<h1>404</h1>")
                    return
                rows = data.listing_rows(page_number)
                if not rows:
                    self._send(404, "<h1>404</h1>")
                    return
                links = []
                for row in rows:
                    label = escape(_value(row["primary_title"]))
                    if row["start_year"] is not None:
                        label += f" ({row['start_year']})"
                    links.append(f'<li><a href="/title/{escape(row["tconst"])}/">{label}</a></li>')
                html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>IMDb Movie Index {page_number}</title></head><body>
<main data-page-type="listing">
<h1>Movie Index Page {page_number}</h1><ul>{''.join(links)}</ul>
</main></body></html>"""
                self._send(200, html)
                return

            if path.startswith("/title/"):
                parts = [p for p in path.split("/") if p]
                if len(parts) != 2 or parts[0] != "title":
                    self._send(404, "<h1>404</h1>")
                    return
                row = data.movie(parts[1])
                if row is None:
                    self._send(404, "<h1>404</h1>")
                    return
                self._send(200, _movie_html(row))
                return

            self._send(404, "<h1>404</h1>")

    return MirrorHandler


class MirrorServer:
    def __init__(self, source_db, host="127.0.0.1", port=8765, page_size=5000, movie_limit=0, pool_size=24):
        self.data = MirrorData(source_db, page_size=page_size, movie_limit=movie_limit, pool_size=pool_size)
        self.httpd = ThreadingHTTPServer((host, port), create_handler(self.data))
        self.httpd.daemon_threads = True
        self.httpd.allow_reuse_address = True
        self.host = host
        self.port = self.httpd.server_address[1]
        self.thread = None

    @property
    def seed_url(self):
        return f"http://{self.host}:{self.port}/movies/"

    @property
    def allowed_netloc(self):
        return f"{self.host}:{self.port}"

    def start(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=5)
        self.data.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
