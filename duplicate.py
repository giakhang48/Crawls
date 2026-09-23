import hashlib


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


class DuplicateDetector:
    """Detect exact duplicate document content using SHA-256."""

    def __init__(self):
        self.fingerprints = set()

    def add_hash(self, hash_hex: str):
        if hash_hex:
            self.fingerprints.add(hash_hex)

    def is_duplicate(self, content: str):
        fp = fingerprint(content)
        if fp in self.fingerprints:
            return True, fp
        self.fingerprints.add(fp)
        return False, fp
