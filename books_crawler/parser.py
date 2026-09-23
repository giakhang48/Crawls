from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


IGNORED_SCHEMES = ("mailto:", "javascript:", "tel:")
IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".css", ".js", ".zip", ".rar", ".pdf",
    ".mp3", ".mp4", ".webm"
)


def normalize_url(base_url, href):
    """Convert a relative link to an absolute, normalized URL."""
    if not href:
        return None

    href = href.strip()

    if href.startswith(IGNORED_SCHEMES) or href == "#":
        return None

    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)

    if parsed.scheme not in {"http", "https"}:
        return None

    # Remove fragment.
    normalized = parsed._replace(fragment="").geturl()

    path = urlparse(normalized).path.lower()
    if path.endswith(IGNORED_EXTENSIONS):
        return None

    return normalized


def is_allowed_url(url, allowed_domains):
    """Return True only for HTTP(S) URLs in the allowed domains."""
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return False

    return parsed.netloc.lower() in {
        domain.lower() for domain in allowed_domains
    }


def parse_page(html, url):
    """Extract useful information and hyperlinks from a page."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title:
        title = soup.title.get_text(" ", strip=True)

    # Remove elements that are not useful as page text.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    content = soup.get_text(" ", strip=True)

    links = []
    for tag in soup.find_all("a", href=True):
        link = normalize_url(url, tag["href"])
        if link:
            links.append(link)

    # Book-specific fields, when the page is a book detail page.
    book_title = ""
    price = ""
    rating = ""
    category = ""

    product_main = soup.select_one(".product_main")
    if product_main:
        heading = product_main.select_one("h1")
        if heading:
            book_title = heading.get_text(" ", strip=True)

        price_tag = product_main.select_one(".price_color")
        if price_tag:
            price = price_tag.get_text(" ", strip=True)

        rating_tag = product_main.select_one(".star-rating")
        if rating_tag:
            classes = rating_tag.get("class", [])
            rating_names = {"One", "Two", "Three", "Four", "Five"}
            rating = next(
                (name for name in classes if name in rating_names),
                ""
            )

    breadcrumb = soup.select(".breadcrumb li a")
    if breadcrumb:
        category = breadcrumb[-1].get_text(" ", strip=True)

    return {
        "title": title,
        "content": content,
        "links": links,
        "book_title": book_title,
        "price": price,
        "rating": rating,
        "category": category,
    }
