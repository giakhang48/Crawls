import json
import re
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup

from config import (
    ALLOWED_DOMAINS,
    IGNORED_EXTENSIONS,
    ALLOWED_PATH_PREFIXES,
    BLOCKED_PATH_PREFIXES,
)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Bỏ fragment vì #... không tạo tài nguyên HTTP khác.
    path = parsed.path or "/"

    # Chuẩn hóa trailing slash nhẹ nhàng, nhưng giữ root "/".
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,
        "",
    ))
    return normalized


def allowed_domain(netloc: str) -> bool:
    host = netloc.lower().split(":")[0]
    return host in ALLOWED_DOMAINS


def is_web_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"}


def has_ignored_extension(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in IGNORED_EXTENSIONS)


def is_focused_path(path: str) -> bool:
    """Kiểm tra path có nằm trong phạm vi focused crawling hay không."""
    if any(path.startswith(p) for p in BLOCKED_PATH_PREFIXES):
        return False

    # Nếu không cấu hình allow-list, coi như cho phép mọi path (trừ blocked).
    if not ALLOWED_PATH_PREFIXES:
        return True

    return any(path.startswith(p) for p in ALLOWED_PATH_PREFIXES)


def should_ignore_raw_href(href: str) -> bool:
    if not href:
        return True

    h = href.strip().lower()
    return (
        h.startswith("mailto:")
        or h.startswith("javascript:")
        or h.startswith("tel:")
        or h.startswith("data:")
        or h.startswith("#")
    )


def _extract_json_ld_movie(soup: BeautifulSoup) -> dict:
    """
    Trang phim trên Letterboxd thường nhúng metadata dạng schema.org/Movie
    trong <script type="application/ld+json">. Trích ra nếu có; nếu không
    tìm thấy, trả về dict rỗng (không phải lỗi — nhiều trang không phải
    trang phim, ví dụ trang danh sách, sẽ không có khối này).
    """
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]

        for item in candidates:
            if not isinstance(item, dict):
                continue
            if item.get("@type") != "Movie":
                continue

            director_field = item.get("director")
            if isinstance(director_field, list):
                directors = ", ".join(
                    d.get("name", "") for d in director_field if isinstance(d, dict)
                )
            elif isinstance(director_field, dict):
                directors = director_field.get("name", "")
            else:
                directors = ""

            rating = item.get("aggregateRating") or {}

            return {
                "film_name": item.get("name", ""),
                "release_year": str(item.get("dateCreated") or item.get("datePublished") or ""),
                "director": directors,
                "rating_value": rating.get("ratingValue"),
                "rating_count": rating.get("ratingCount"),
            }

    return {}


def extract_page_info(soup: BeautifulSoup, url: str, depth: int, status_code: int):
    parsed = urlparse(url)
    title = ""

    if soup.title:
        title = soup.title.get_text(" ", strip=True)

    film_meta = _extract_json_ld_movie(soup)

    # Loại script/style/noscript trước khi lấy visible-ish text.
    # (Làm sau khi đã đọc JSON-LD ở trên, vì JSON-LD nằm trong <script>.)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    content = soup.get_text(" ", strip=True)
    content = re.sub(r"\s+", " ", content)

    return {
        "url": url,
        "domain": parsed.netloc,
        "title": title,
        "content": content,
        "depth": depth,
        "status_code": status_code,
        "film_name": film_meta.get("film_name"),
        "release_year": film_meta.get("release_year"),
        "director": film_meta.get("director"),
        "rating_value": film_meta.get("rating_value"),
        "rating_count": film_meta.get("rating_count"),
    }


def extract_links(soup: BeautifulSoup, current_url: str):
    result = []

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()

        if should_ignore_raw_href(href):
            continue

        absolute = normalize_url(urljoin(current_url, href))

        if not is_web_url(absolute):
            continue

        parsed = urlparse(absolute)

        if not allowed_domain(parsed.netloc):
            continue

        if has_ignored_extension(absolute):
            continue

        if not is_focused_path(parsed.path):
            continue

        result.append(absolute)

    # Loại trùng nhưng giữ thứ tự.
    return list(dict.fromkeys(result))
