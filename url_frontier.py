from collections import deque


class URLFrontier:
    """BFS URL Frontier.

    queued prevents the same URL being inserted into the queue twice.
    visited prevents a crawled URL being requested again.
    """

    def __init__(self):
        self.queue = deque()
        self.queued = set()
        self.visited = set()

    def add(self, url, depth):
        if url in self.visited or url in self.queued:
            return False
        self.queue.append((url, depth))
        self.queued.add(url)
        return True

    def get(self):
        if not self.queue:
            return None
        url, depth = self.queue.popleft()
        self.queued.discard(url)
        return url, depth

    def peek_depth(self):
        if not self.queue:
            return None
        return self.queue[0][1]

    def get_same_depth_batch(self, max_items):
        """Pop up to max_items URLs from the current BFS depth only."""
        if not self.queue:
            return []
        depth = self.queue[0][1]
        batch = []
        while self.queue and len(batch) < max_items and self.queue[0][1] == depth:
            url, d = self.queue.popleft()
            self.queued.discard(url)
            batch.append((url, d))
        return batch

    def mark_visited(self, url):
        self.visited.add(url)

    def empty(self):
        return not self.queue

    def __len__(self):
        return len(self.queue)
