import re
from urllib.parse import urljoin, urlparse, urlunparse, unquote

from bs4 import BeautifulSoup

import config

YEAR_RE = re.compile(r"\b(?:18|19|20)\d{2}\b")
LIST_TITLE_RE = re.compile(r"^List_of_films:_(?:numbers|[A-Z](?:[–-][A-Z])*)$", re.I)


def normalize_url(url: str) -> str:
    """Normalize a Wikipedia URL for duplicate control."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip fragment and query. The assignment corpus targets canonical article pages.
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", "", ""))


def wikipedia_title_from_url(url: str):
    parsed = urlparse(url)
    if not parsed.path.startswith("/wiki/"):
        return None
    return unquote(parsed.path[len("/wiki/"):])


def classify_page(url: str) -> str:
    title = wikipedia_title_from_url(url)
    if title == "Lists_of_films":
        return "root"
    if title and LIST_TITLE_RE.match(title):
        return "list"
    return "movie"


def is_allowed_article_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return False, "non_http"

    if parsed.netloc.lower() not in config.ALLOWED_NETLOCS:
        return False, "outside_domain"

    lower_path = parsed.path.lower()
    if any(lower_path.endswith(ext) for ext in config.IGNORED_EXTENSIONS):
        return False, "ignored_extension"

    if not parsed.path.startswith("/wiki/"):
        return False, "not_article_path"

    title = wikipedia_title_from_url(url)
    if not title:
        return False, "missing_title"

    if any(title.startswith(prefix) for prefix in config.DISALLOWED_TITLE_PREFIXES):
        return False, "disallowed_namespace"

    return True, "accepted"


def _content_root(soup: BeautifulSoup):
    return (
        soup.select_one("div.mw-parser-output")
        or soup.select_one("#mw-content-text")
        or soup.find("main")
        or soup.body
        or soup
    )


def clean_article_text(soup: BeautifulSoup) -> str:
    root = _content_root(soup)

    # Work on a copy so link extraction can still use the original soup.
    root_soup = BeautifulSoup(str(root), "lxml")
    for selector in [
        "script", "style", "noscript", "sup.reference", "ol.references",
        "div.reflist", "table.navbox", "div.navbox", "table.vertical-navbox",
        "div.printfooter", "span.mw-editsection", "div.hatnote",
    ]:
        for node in root_soup.select(selector):
            node.decompose()

    return root_soup.get_text(" ", strip=True)


def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.select_one("h1#firstHeading") or soup.select_one("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(" ", strip=True).replace(" - Wikipedia", "")
    else:
        title = ""

    content = clean_article_text(soup)
    return {
        "title": title,
        "content": content,
        "page_type": classify_page(url),
        "soup": soup,
    }


def extract_root_list_links(soup: BeautifulSoup, current_url: str):
    """From Lists_of_films, keep only the alphabetic A-Z and numbers list pages."""
    accepted = []
    seen = set()
    root = _content_root(soup)

    for a in root.find_all("a", href=True):
        absolute = normalize_url(urljoin(current_url, a["href"]))
        title = wikipedia_title_from_url(absolute)
        if title and LIST_TITLE_RE.match(title):
            if absolute not in seen:
                seen.add(absolute)
                accepted.append(absolute)

    return accepted


def extract_movie_links_from_list(soup: BeautifulSoup, current_url: str):
    """Extract film-article candidates from a List_of_films:_X page.

    Focus heuristic:
    - candidate anchor must be inside a list item
    - the list item's visible text must contain a film year (18xx/19xx/20xx)
    - article must stay in en.wikipedia.org /wiki/
    - reject Wikipedia namespaces and other List_of_* pages

    This avoids following cast/director/reference/navigation links while still
    discovering movie pages from the list itself.
    """
    accepted = []
    seen = set()
    root = _content_root(soup)

    for li in root.find_all("li"):
        li_text = li.get_text(" ", strip=True)
        if not YEAR_RE.search(li_text):
            continue

        for a in li.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if not text or YEAR_RE.fullmatch(text):
                continue

            absolute = normalize_url(urljoin(current_url, a["href"]))
            allowed, _ = is_allowed_article_url(absolute)
            if not allowed:
                continue

            title = wikipedia_title_from_url(absolute) or ""
            if title.startswith("List_of_") or title.startswith("Lists_of_"):
                continue
            if title == "Lists_of_films":
                continue

            if absolute not in seen:
                seen.add(absolute)
                accepted.append(absolute)

    return accepted


def extract_focused_links(html: str, current_url: str):
    """Return (accepted_links, rejected_count, rejection_reasons)."""
    soup = BeautifulSoup(html, "lxml")
    page_type = classify_page(current_url)

    reasons = {}
    rejected = 0

    if page_type == "root":
        raw = extract_root_list_links(soup, current_url)
    elif page_type == "list":
        raw = extract_movie_links_from_list(soup, current_url)
    else:
        # Focused crawler stops traversal at movie article pages.
        raw = []

    accepted = []
    seen = set()
    for url in raw:
        ok, reason = is_allowed_article_url(url)
        if not ok:
            rejected += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        if url in seen:
            rejected += 1
            reasons["duplicate_normalized"] = reasons.get("duplicate_normalized", 0) + 1
            continue
        seen.add(url)
        accepted.append(url)

    return accepted, rejected, reasons


def extract_infobox_metadata(soup: BeautifulSoup) -> dict:
    """Best-effort metadata from a Wikipedia film infobox."""
    result = {
        "directed_by": None,
        "release_date": None,
        "running_time": None,
        "country": None,
        "language": None,
    }

    infobox = soup.select_one("table.infobox")
    if not infobox:
        return result

    labels = {
        "Directed by": "directed_by",
        "Release date": "release_date",
        "Running time": "running_time",
        "Country": "country",
        "Language": "language",
        "Languages": "language",
    }

    for tr in infobox.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        label = th.get_text(" ", strip=True)
        key = labels.get(label)
        if key:
            result[key] = td.get_text(" ", strip=True)

    return result


def is_probable_film_article(parsed: dict) -> bool:
    """Quality heuristic; used for analysis, not for frontier discovery."""
    soup = parsed["soup"]
    infobox = soup.select_one("table.infobox")
    if not infobox:
        return False

    infobox_text = infobox.get_text(" ", strip=True)
    signals = ("Directed by", "Release date", "Running time", "Produced by")
    return sum(1 for s in signals if s in infobox_text) >= 2
