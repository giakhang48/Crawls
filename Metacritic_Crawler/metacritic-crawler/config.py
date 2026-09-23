"""Task 1: đổi cấu hình ở đây, không cần sửa thuật toán BFS."""
from pathlib import Path

TOPIC = "Movies & Entertainment"
# Phần việc cá nhân: chỉ Metacritic. Nhóm tổng hợp các nguồn của thành viên khác.
# Kiểm tra Terms of Use trước khi chạy; robots.txt được kiểm tra tự động.
SEED_URLS = [
    "https://www.metacritic.com/browse/movie/",
]
ALLOWED_DOMAINS = {"www.metacritic.com"}
# Chỉ trang danh sách phim và trang phim; không đi sang TV, game, người dùng.
PATH_PATTERNS = {
    "www.metacritic.com": [r"^/browse/movie(?:/.*)?$", r"^/movie/[^/]+/?$"],
}
MAX_PAGES = 100               # Số trang HTML HTTP 200 lưu thành công
MAX_DEPTH = 3                 # Seed = depth 0
MAX_REQUESTS = 300            # Giới hạn phụ: số request nội dung, kể cả lỗi
REQUEST_TIMEOUT = 15
CRAWL_DELAY = 2.0             # Chờ tối thiểu giữa các request cùng host
USER_AGENT = "SEG301MovieCrawler/1.0 (educational lab)"
DATA_DIR = Path(__file__).resolve().parent / "data"
