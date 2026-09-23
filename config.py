from pathlib import Path

TOPIC = "Movies & Entertainment"
SITE_NAME = "Wikipedia Movies"

SEED_URL = "https://en.wikipedia.org/wiki/Lists_of_films"
ROBOTS_URL = "https://en.wikipedia.org/robots.txt"
ALLOWED_NETLOCS = {"en.wikipedia.org"}

# Polite, transparent academic crawler. Do NOT pretend to be a browser.
USER_AGENT = "SEG301WikipediaMoviesBot/1.1 (https://github.com/giakhang48/Crawls; academic coursework)"

# The focused crawl topology is:
# depth 0: Lists_of_films
# depth 1: List_of_films:_A ... Z + numbers
# depth 2: individual film article candidates discovered from those list pages
MAX_DEPTH = 2

# Set high enough to allow the A-Z frontier to finish naturally.
# The crawler can also be run with --max-pages to override this.
MAX_PAGES = 100_000

REQUEST_TIMEOUT = 30
CRAWL_DELAY = 2.0
MAX_RETRIES = 6

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "wikipedia_movies.db"

# Minimum text length for a successfully fetched article to be considered useful.
MIN_CONTENT_CHARS = 120

# Non-HTML / non-article resources to reject.
IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".json", ".xml", ".pdf", ".zip", ".gz", ".mp3",
    ".mp4", ".avi", ".mov", ".webm", ".ogg", ".wav", ".woff", ".woff2",
}

# Wikipedia namespaces / paths not relevant to the focused movie corpus.
DISALLOWED_TITLE_PREFIXES = (
    "Special:", "Wikipedia:", "Help:", "Template:", "Template_talk:",
    "Talk:", "User:", "User_talk:", "Category:", "Portal:", "File:",
    "Media:", "MediaWiki:", "Draft:", "Module:", "Book:",
)
