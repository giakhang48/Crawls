"""Task 4 + 5: chuẩn hóa, lọc URL và tách nội dung HTML."""
import re
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit, unquote
from bs4 import BeautifulSoup

FILE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
                   ".css", ".js", ".zip", ".pdf", ".mp4", ".mp3", ".woff", ".woff2"}
TRACKING_KEYS = {"fbclid", "gclid", "ref", "ref_"}


def normalize_url(href, base_url):
    try:
        p = urlsplit(urljoin(base_url, href.strip()))
        if p.scheme.lower() not in {"http", "https"} or not p.hostname:
            return None
        if p.username or p.password:
            return None
        host = p.hostname.lower()
        port = p.port  # Có thể ValueError nếu URL hỏng
        if port and (p.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
            host += f":{port}"
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS]
        # Giữ thứ tự query và dấu / cuối: chúng có thể mang ý nghĩa ở server.
        return urlunsplit((p.scheme.lower(), host, p.path or "/", urlencode(query), ""))
    except (ValueError, TypeError):
        return None


def is_allowed(url, config):
    p = urlsplit(url)
    if p.netloc not in config.ALLOWED_DOMAINS:
        return False
    if PurePosixPath(unquote(p.path).lower()).suffix in FILE_EXTENSIONS:
        return False
    return any(re.fullmatch(pattern, p.path)
               for pattern in config.PATH_PATTERNS.get(p.netloc, []))


def parse_page(html, url):
    # Nhận bytes để BeautifulSoup đọc charset/meta trong HTML.
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    base_tag = soup.find("base", href=True)
    base = urljoin(url, base_tag["href"]) if base_tag else url
    hrefs = [tag["href"] for tag in soup.find_all("a", href=True)]
    for tag in soup.select("script, style, noscript, template, nav, header, footer, [hidden]"):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    content = main.get_text(" ", strip=True)
    return title, content, hrefs, base

