import unicodedata
import re


def normalize_query(q: str) -> str:
    """Unicode-normalize, lowercase, trim, collapse internal whitespace."""
    q = unicodedata.normalize("NFC", q)
    q = q.lower().strip()
    q = re.sub(r"\s+", " ", q)
    return q
