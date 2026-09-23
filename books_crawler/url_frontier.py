from collections import deque


class URLFrontier:
    """Simple FIFO URL frontier for breadth-first crawling."""

    def __init__(self):
        self.queue = deque()
        self.queued = set()

    def add(self, url, depth):
        if url in self.queued:
            return False

        self.queue.append((url, depth))
        self.queued.add(url)
        return True

    def pop(self):
        if not self.queue:
            return None
        return self.queue.popleft()

    def empty(self):
        return not self.queue

    def __len__(self):
        return len(self.queue)
