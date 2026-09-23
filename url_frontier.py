from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class FrontierItem:
    url: str
    depth: int


class URLFrontier:
    """BFS URL frontier implemented with deque + queued + visited sets."""

    def __init__(self):
        self.queue = deque()
        self.queued = set()
        self.visited = set()

    def add(self, url: str, depth: int) -> bool:
        if url in self.visited or url in self.queued:
            return False
        self.queue.append(FrontierItem(url, depth))
        self.queued.add(url)
        return True

    def get(self):
        if not self.queue:
            return None
        item = self.queue.popleft()
        self.queued.discard(item.url)
        return item

    def mark_visited(self, url: str):
        self.visited.add(url)
        self.queued.discard(url)

    def is_visited(self, url: str) -> bool:
        return url in self.visited

    def empty(self) -> bool:
        return not self.queue

    def __len__(self):
        return len(self.queue)

    def restore_visited(self, urls):
        for url in urls:
            self.visited.add(url)
