TOPIC = "Movies & Entertainment"

# Trang danh sách phim phổ biến là điểm khởi đầu tốt: nhiều link ra
# trang chi tiết từng phim (/film/<slug>/), đúng trọng tâm chủ đề.
SEED_URLS = [
    "https://letterboxd.com/films/popular/",
]

ALLOWED_DOMAINS = {
    "letterboxd.com",
    "www.letterboxd.com",
}

# --- Focused crawling ---
# Chỉ đi theo các link nằm trong những prefix này. Mục đích:
#   1) Giữ crawler đúng chủ đề phim, không lan sang trang cá nhân
#      người dùng, diary, review riêng lẻ...
#   2) Giảm số lượng request không cần thiết -> lịch sự hơn với server.
# Để rỗng () nếu muốn crawl toàn bộ domain (không khuyến khích).
ALLOWED_PATH_PREFIXES = (
    "/film/",
    "/films/popular/",
)

# Các path chắc chắn không nên crawl, bất kể robots.txt có nhắc tới hay không
# (trang cần đăng nhập, endpoint nội bộ, tìm kiếm...).
BLOCKED_PATH_PREFIXES = (
    "/search",
    "/settings",
    "/login",
    "/signup",
    "/j/",
    "/api/",
    "/ajax/",
)

MAX_DEPTH = 2
MAX_PAGES = 20
REQUEST_TIMEOUT = 10

# Letterboxd là site lớn hơn nhiều so với một domain thử nghiệm nhỏ,
# nên tăng delay để lịch sự hơn và giảm rủi ro bị coi là traffic bất thường.
CRAWL_DELAY = 3.0

USER_AGENT = (
    "SEG301-FocusedCrawler/1.0 "
    "(educational assignment; contact: replace-with-your-email@example.com)"
)

# Một số site trả 403 cho request chỉ có mỗi User-Agent mà thiếu các header
# tiêu chuẩn khác mà hầu như mọi HTTP client tử tế đều gửi. Đây KHÔNG phải
# giả mạo trình duyệt — User-Agent vẫn khai báo trung thực là bot, chỉ là
# gửi đủ header thông thường.
EXTRA_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DATABASE_PATH = "data/crawler.db"

IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".css", ".js", ".zip", ".pdf", ".mp4",
    ".webm", ".ico", ".woff", ".woff2", ".ttf",
}

# QUAN TRỌNG: đây chỉ là danh sách tham khảo để log rõ hơn.
# RobotFileParser trong crawler.py mới là nguồn quyết định chính — nó tự tải
# https://letterboxd.com/robots.txt lúc chạy và tự động chặn đúng theo đó.
# Trước khi chạy thật, hãy tự mở robots.txt trong trình duyệt và cập nhật
# danh sách này cho khớp với tình trạng thực tế tại thời điểm bạn chạy,
# vì nội dung robots.txt có thể thay đổi theo thời gian.
KNOWN_DISALLOWED_PREFIXES = (
    "/search",
    "/settings",
)
