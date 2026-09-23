# SEG301 Lab - Metacritic Movie Crawler (phần việc cá nhân)

## 1. Bài này cần làm gì?

Viết chương trình Python bắt đầu từ một số URL phim. Chương trình tải trang HTML,
lấy tiêu đề và nội dung, tìm các liên kết phim khác rồi tiếp tục tải theo BFS.
Kết quả được lưu vào SQLite để dùng cho bài sau.

Phân công của bạn: chỉ crawl **Metacritic**. Yêu cầu ít nhất 2 domain trong PDF áp dụng
cho **bài nộp chung của nhóm**, không bắt buộc mỗi thành viên làm 2 domain.

Theo PDF: dùng Python, Requests, BeautifulSoup, SQLite;
giới hạn độ sâu và số trang; tránh URL trùng; lưu pages/links; thống kê thực tế.
Chưa làm tokenization, stopword removal, stemming, lemmatization hay TF-IDF.
Số 100 trang/depth 3 là cấu hình ví dụ trong đề, không phải bằng chứng đã thu thập 100 trang.

## 2. Nguồn phim và seed URLs

Nguồn duy nhất: **Metacritic**, thuộc chủ đề Movies & Entertainment.

- Domain: `www.metacritic.com`.
- Seed: https://www.metacritic.com/browse/movie/
- Trang phim: `/movie/<slug>/`.
- Trang danh sách: `/browse/movie/...`.
- Link website khác, chuyên mục game/TV và trang người dùng đều bị loại.

**Tình trạng:** code đã được kiểm thử cục bộ; chưa có kết quả crawl Metacritic thật
được xác minh. Lần truy cập trước từ môi trường tạo code bị timeout.
Trước khi chạy, kiểm tra Terms of Use của website theo yêu cầu đề bài.
Code tự kiểm tra https://www.metacritic.com/robots.txt ở mỗi lần chạy.
Robots cho phép đường dẫn không đồng nghĩa điều khoản cho phép mọi cách thu thập.
Nếu gặp chặn truy cập, chương trình ghi lại và dừng host; không dùng proxy/giả Googlebot để vượt chặn.

## 3. Cài đặt trên Windows

1. Giải nén ZIP và mở thư mục `metacritic-crawler` bằng VS Code.
2. Chọn Terminal > New Terminal. Terminal phải ở thư mục có `main.py`.
3. Kiểm tra Python: `py --version` (Python 3.10 trở lên).
4. Tạo môi trường và cài thư viện:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Không cần activate; dùng trực tiếp python.exe trong .venv để tránh lỗi PowerShell ExecutionPolicy.
SQLite có sẵn trong Python, không cài bằng pip.
Nếu `py` không được nhận diện nhưng đã có Python, thử thay `py` bằng `python`.

## 4. Chạy từng bước

Kiểm tra thuật toán bằng server cục bộ, không cần truy cập website phim:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Dữ liệu của kiểm thử là HTML tự tạo và được xóa sau kiểm thử; không dùng làm kết quả lab.

Sau khi kiểm tra chính sách website, chạy Internet với giới hạn nhỏ:

```powershell
.\.venv\Scripts\python.exe main.py --max-pages 10 --max-depth 1 --max-requests 30
```

Nếu đọc được nội dung phim từ Metacritic, chạy cấu hình lớn hơn:

```powershell
.\.venv\Scripts\python.exe main.py --max-pages 100 --max-depth 3
```

Chương trình tạo thư mục `data/run_<thời gian>/` cho từng lần chạy, chứa:

- `crawler.db`: trang, liên kết và nhật ký lỗi.
- `summary.json`: thống kê tính từ lần chạy.
- `RESULTS.md`: kết quả để đưa vào báo cáo/README nộp bài.

Mỗi lần chạy độc lập; không xóa kết quả cũ, không tiếp tục frontier của lần trước.
Nhấn Ctrl+C để dừng và giữ kết quả đã lưu.
Chạy trên macOS/Linux: dùng `python3 -m venv .venv`, sau đó `.venv/bin/python` thay đường dẫn Windows.

## 5. Mỗi file làm gì? Đối chiếu 9 task

| Task | File | Công việc |
|---|---|---|
| 1 | config.py | Chủ đề, seed, domain, depth, max pages, timeout, delay |
| 2 | url_frontier.py | Quản lý queue bằng deque |
| 3 | crawler.py | Gửi request, đo response time, ghi lỗi |
| 4 | parser.py | Lấy title và text; bỏ script/style/menu cơ bản |
| 5 | parser.py + config.py | Link tương đối, chuẩn hóa, lọc domain/protocol/file/chuyên mục |
| 6 | crawler.py | Seed depth 0; link con depth + 1 |
| 7 | url_frontier.py | seen ngăn thêm trùng, visited theo dõi URL đã xử lý |
| 8 | database.py | Tạo bảng và lưu SQLite |
| 9 | crawler.py + main.py | Ghép toàn bộ quy trình và in thống kê |

File bổ sung: `robots.py` kiểm tra robots; `inspect_db.py` xem dữ liệu;
`test_crawler.py` kiểm thử cục bộ.

## 6. Hiểu BFS bằng ví dụ phim

Giả sử seed S là trang danh sách phim Metacritic. S dẫn tới phim A và B;
trang A có liên kết tới phim C.

Thứ tự BFS: S, A, B, C.

- S: depth 0.
- A, B: depth 1.
- C: depth 2.

`frontier.append((url, depth))` thêm cuối hàng đợi.
`frontier.popleft()` lấy đầu hàng đợi.
Vì URL vào trước được xử lý trước nên crawler đi hết lớp nông trước khi tới lớp sâu.
Khi MAX_DEPTH=1, vẫn tải A/B và lưu liên kết phát hiện trên chúng,
nhưng không đưa C vào hàng đợi để tải.

`seen` chứa cả URL đang chờ lẫn đã xử lý. Nếu A xuất hiện ở nhiều trang, chỉ đưa A vào queue một lần.
`visited` chứa URL đã lấy ra khỏi queue, kể cả URL bị robots chặn. Không đồng nghĩa tải thành công.

## 7. Cấu hình và quy tắc lọc

Mặc định: MAX_PAGES=100, MAX_DEPTH=3, MAX_REQUESTS=300, timeout=15 giây, delay=2 giây.
Delay 2 giây giảm mật độ request; nếu robots yêu cầu lớn hơn thì dùng mức lớn hơn.
Crawler đơn luồng để dễ theo dõi BFS.

- Chỉ http/https; bỏ mailto/javascript/tel và URL hỏng.
- Khớp hostname chính xác với ALLOWED_DOMAINS; không tự chấp nhận mọi subdomain.
- Bỏ file ảnh, video, JS, CSS, PDF, ZIP và một số tài nguyên tĩnh khác.
- Metacritic: chỉ /browse/movie... và /movie/<slug>.
- Bỏ #fragment, tham số utm_*, fbclid, gclid, ref/ref_. Giữ query khác như page.
- Giữ nguyên dấu / cuối, http/https và thứ tự tham số vì không phải website nào cũng coi chúng tương đương.
- URL khác nhau nhưng nội dung giống nhau chưa được gộp: đề lab yêu cầu chống trùng URL.
- Không tự theo HTTP redirect. Ghi mã 3xx và Location trong events. Sửa seed thành URL cuối hợp lệ sau khi kiểm tra.
- Lỗi robots, robots trả HTML hoặc redirect robots: bỏ origin thay vì suy đoán được phép.
- robots trả 404/410: coi không có file robots; vẫn phải tuân thủ điều khoản.
- HTTP 401/403/429: ghi lỗi và ngừng request nội dung tới host trong lần chạy.
- Không tải dữ liệu JavaScript bằng trình duyệt. Trang phụ thuộc JS có thể ít nội dung/liên kết.

`robots.py` có xử lý nhóm User-Agent, Allow/Disallow, wildcard *, dấu $ và Crawl-delay.
Đây là matcher đơn giản cho đường dẫn ASCII của lab; không thay thế thư viện REP đầy đủ
cho mọi trường hợp Unicode/percent-encoding. Khi thay nguồn, kiểm tra các rule của nguồn mới.

## 8. Thiết kế database và cách xem

**pages**: mỗi bản ghi là một trang HTML HTTP 200 lưu thành công.
Các cột: id, url (UNIQUE), domain, title, content, depth, status_code, crawled_at,
response_time (bổ sung). `title` là tiêu đề trang, chưa tách riêng tên phim/đạo diễn/điểm số.

**links**: một cạnh source_url -> target_url sau khi chuẩn hóa và qua bộ lọc URL.
Cặp source-target là UNIQUE. Có thể lưu cạnh tới URL chưa tải, bị giới hạn depth hoặc robots chặn.

**events**: ghi kiểm tra robots, HTTP lỗi, timeout, challenge và các trang bị bỏ qua sau request.
Nội dung lỗi không trộn vào pages.

Xem lần chạy mới nhất:

```powershell
.\.venv\Scripts\python.exe inspect_db.py
```

Xem lần cụ thể:

```powershell
.\.venv\Scripts\python.exe inspect_db.py --db data/run_THOI_GIAN/crawler.db
```

Các câu SQL hữu ích (có thể mở database bằng công cụ SQLite nếu đã có):

```sql
SELECT id, title, url, depth FROM pages LIMIT 10;
SELECT domain, COUNT(*) AS total FROM pages GROUP BY domain;
SELECT depth, COUNT(*) AS total FROM pages GROUP BY depth;
SELECT kind, status_code, COUNT(*) FROM events GROUP BY kind, status_code;
SELECT source_url, target_url FROM links LIMIT 10;
```

## 9. Hiểu thống kê và chuẩn bị nộp

- pages_crawled: số trang HTML 200 thực sự lưu vào pages.
- page_requests: số request nội dung, không tính robots.
- unique_urls_discovered: seed và link duy nhất qua bộ lọc URL, kể cả chưa tải.
- skipped_url_occurrences: số lượt bỏ qua, không phải số URL duy nhất.
- failed_requests: request nội dung gặp lỗi mạng, HTTP khác 200, hoặc challenge phát hiện theo title.
- http_statuses: mọi response nội dung, kể cả lỗi, non-HTML và challenge; không tính robots.
- by_depth/by_domain: phân bố trang lưu thành công.
- maximum_depth_configured khác maximum_depth_reached: giới hạn và độ sâu thực sự đạt được.
- configured_domains: domain được cấu hình (chỉ www.metacritic.com).
- domains_collected: số domain có trang lưu thành công; bình thường là 1 trong phần việc này.
- all_configured_domains_have_pages: true nếu Metacritic đã có trang lưu thành công;
  chỉ phản ánh có dữ liệu, không xác nhận nội dung đúng hoặc hoàn thành toàn bộ bài nhóm.
- stop_reason: hết frontier, đủ số trang, đủ số request hoặc người dùng dừng.

Đừng suy luận HTTP 200 luôn là nội dung phim: xem thử title/content trong database.
Một số challenge trả 200; bộ lọc title chỉ nhận diện một số trường hợp phổ biến.

Sau lần chạy cuối, chép phần thống kê trong RESULTS.md vào mục “Kết quả crawl thực tế” bên dưới.
Nếu Metacritic bị chặn, ghi rõ lỗi thực tế và trao đổi với nhóm/thầy về cách xử lý. Chụp terminal và vài dòng pages/links
để bạn thuận tiện minh họa khi báo cáo. Không dùng kết quả unit test làm số liệu crawl Internet.

Nộp source code, requirements.txt, README.md, cùng crawler.db và RESULTS.md của lần chạy cuối.
Không cần nộp .venv hoặc __pycache__.

### Kết quả crawl thực tế

Chưa có kết quả Internet đã xác minh. Điền bằng RESULTS.md do lần chạy của bạn tạo ra.
Database chỉ có Metacritic là đúng phạm vi cá nhân. Nếu không có trang nào, chưa có dữ liệu thực tế để nộp.
Nhóm kết hợp phần của bạn với nguồn khác để đáp ứng yêu cầu ít nhất 2 domain.

## 10. Lỗi hay gặp

| Hiện tượng | Cách xử lý |
|---|---|
| No module named requests/bs4 | Chạy pip bằng đúng .venv/python.exe như mục 3 |
| Không tìm thấy main.py | Mở terminal đúng thư mục sau giải nén |
| Pages = 0 | Xem dòng robots và events; không phải cứ có DB là đã thu thập thành công |
| HTTP 301/302 | Xem Location; kiểm tra URL cuối rồi cập nhật seed |
| HTTP 403/429, CAPTCHA | Dừng nguồn đó; kiểm tra quyền truy cập, chọn nguồn khác khi cần |
| Timeout/connection error | Kiểm tra mạng; lỗi đã được ghi, crawler tiếp tục xử lý URL còn lại nếu có |
| Ít link hoặc nội dung rỗng | Kiểm tra HTML nguồn; website có thể render bằng JS |
| Chỉ có 1 domain | Đúng phạm vi của bạn: Metacritic |

Bạn không cần thêm website khác vào phần việc cá nhân. Khi làm việc nhóm, gửi source,
requirements.txt, README.md và thư mục kết quả thực tế cho người tổng hợp.
Các thành viên có thể giữ chung cấu trúc bảng pages/links để thuận tiện hợp nhất dữ liệu.

## 11. Giải thích ngắn khi được hỏi

- **Seed URL là gì?** Điểm bắt đầu để tìm các trang khác qua hyperlink.
- **Frontier là gì?** Hàng đợi URL chờ xử lý, kèm depth.
- **Tại sao BFS?** Xử lý trang gần seed trước, thuận tiện kiểm soát depth.
- **Tại sao dùng set?** Kiểm tra URL đã thấy nhanh, trung bình O(1).
- **Requests và BeautifulSoup khác gì?** Requests tải HTML; BeautifulSoup phân tích HTML.
- **Vì sao có cả pages và links?** pages lưu nội dung; links lưu quan hệ giữa các trang.
- **Focused ở đâu?** Giới hạn domain phim và đường dẫn chuyên mục phim.
- **MAX_PAGES là số phim không?** Không. Là số trang HTML, gồm cả trang danh sách.
- **Depth tính theo dấu / trong URL không?** Không. Tính số bước theo hyperlink từ seed.
- **Có cần machine learning không?** Không ở lab này.

## 12. Tài liệu

- Đề PDF người dùng cung cấp: 21_09_2026___755bde41-6ce6-4515-8cda-704b57491359(1).pdf.
- https://shandyprofile.github.io/posts/seg301_03_crawls_and_feeds/
- https://www.metacritic.com/robots.txt

Kiểm tra kỹ thuật: bộ kiểm thử cục bộ kiểm tra BFS, depth, trùng URL, robots, HTTP 404,
một host thử nghiệm, bộ lọc riêng cho Metacritic, lưu pages/links, UTF-8 và thống kê. Đây không phải xác nhận website thật crawl được.
