from collections import deque


class URLFrontier:
    """FIFO queue dùng cho BFS."""

    def __init__(self):
        self._queue = deque()
        self._queued = set()

    def add(self, url: str, depth: int) -> bool:
        if url in self._queued:
            return False
        self._queue.append((url, depth))
        self._queued.add(url)
        return True

    def pop(self):
        url, depth = self._queue.popleft()
        self._queued.discard(url)
        return url, depth

    def __len__(self):
        return len(self._queue)

    def empty(self):
        return not self._queue
