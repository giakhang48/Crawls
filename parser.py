from collections import Counter
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".zip",
    ".pdf", ".mp4", ".mp3", ".webp", ".ico", ".woff", ".woff2",
)


def normalize_url(url: str) -> str:
    """Normalize URL for frontier de-duplication."""
    p = urlparse(url)
    return urlunparse((
        p.scheme.lower(),
        p.netloc.lower(),
        p.path or "/",
        "",
        p.query,
        "",  # strip fragment
    ))


def extract_page(html: str):
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""

    # The mirror puts the actual page payload in <main>. This avoids indexing
    # navigation/boilerplate while still parsing the real HTTP-delivered HTML.
    content_node = soup.find("main") or soup
    content = content_node.get_text(separator=" ", strip=True)

    page_type = "other"
    if content_node and content_node.has_attr("data-page-type"):
        page_type = content_node.get("data-page-type", "other")

    canonical = ""
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag and canonical_tag.get("href"):
        canonical = canonical_tag["href"].strip()

    return {
        "title": title,
        "content": content,
        "page_type": page_type,
        "canonical_url": canonical,
        "soup": soup,
    }


def _field_text(soup, field):
    node = soup.select_one(f'[data-field="{field}"]')
    return node.get_text(strip=True) if node else None


def _as_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_movie_metadata(page):
    """Extract structured movie fields FROM THE PARSED HTML page."""
    if page["page_type"] != "movie":
        return None
    soup = page["soup"]
    main = soup.find("main")
    tconst = main.get("data-tconst") if main else None
    if not tconst:
        return None
    return {
        "tconst": tconst,
        "primary_title": _field_text(soup, "primary_title"),
        "original_title": _field_text(soup, "original_title"),
        "start_year": _as_int(_field_text(soup, "start_year")),
        "runtime_minutes": _as_int(_field_text(soup, "runtime_minutes")),
        "genres": _field_text(soup, "genres"),
        "average_rating": _as_float(_field_text(soup, "average_rating")),
        "num_votes": _as_int(_field_text(soup, "num_votes")),
        "canonical_url": page.get("canonical_url") or None,
    }


def extract_links_detailed(html, current_url, allowed_netlocs):
    soup = BeautifulSoup(html, "lxml")
    stats = Counter()
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        stats["raw"] += 1
        href = tag.get("href", "").strip()
        if not href:
            stats["empty"] += 1
            continue
        if href.startswith(("mailto:", "javascript:", "tel:")):
            stats["non_web_scheme"] += 1
            continue

        absolute = normalize_url(urljoin(current_url, href))
        p = urlparse(absolute)
        if p.scheme not in {"http", "https"}:
            stats["non_http"] += 1
            continue
        if p.netloc.lower() not in allowed_netlocs:
            stats["outside_domain"] += 1
            continue
        if p.path.lower().endswith(IGNORED_EXTENSIONS):
            stats["ignored_extension"] += 1
            continue
        if absolute in seen:
            stats["duplicate_normalized"] += 1
            continue

        seen.add(absolute)
        links.append(absolute)
        stats["accepted"] += 1

    return links, dict(stats)
