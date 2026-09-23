"""Task 2 + 7: hàng đợi FIFO và chống thêm trùng URL."""
from collections import deque


class URLFrontier:
    def __init__(self):
        self.queue = deque()
        self.seen = set()       # Đã đưa vào queue, kể cả URL đã xử lý
        self.visited = set()    # Đã lấy ra khỏi queue

    def add(self, url, depth):
        if url in self.seen:
            return False
        self.seen.add(url)
        self.queue.append((url, depth))
        return True

    def pop(self):
        url, depth = self.queue.popleft()
        self.visited.add(url)
        return url, depth

    def __bool__(self):
        return bool(self.queue)

