import hashlib


class DuplicateDetector:
    """Exact-content duplicate detector using SHA-256."""

    def __init__(self):
        self._fingerprints = set()

    @staticmethod
    def digest(content: str) -> bytes:
        return hashlib.sha256(content.encode("utf-8")).digest()

    @staticmethod
    def hexdigest(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def is_duplicate(self, content: str) -> bool:
        fp = self.digest(content)
        if fp in self._fingerprints:
            return True
        self._fingerprints.add(fp)
        return False
