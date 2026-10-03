import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from nltk.stem import SnowballStemmer

# ---------------------------------------------------------------------------
# Stopwords — loaded from static file, no network needed
# ---------------------------------------------------------------------------
_STOPWORDS_PATH = Path(__file__).parent / "data" / "stopwords_en.txt"
_STOP_WORDS: set[str] = set(_STOPWORDS_PATH.read_text(encoding="utf-8").split())

# ---------------------------------------------------------------------------
# Stemmer
# ---------------------------------------------------------------------------
_stemmer = SnowballStemmer("english")

@lru_cache(maxsize=50_000)
def _stem(word: str) -> str:
    return _stemmer.stem(word)

# ---------------------------------------------------------------------------
# Protected substitution table  (applied before symbol stripping)
# ---------------------------------------------------------------------------
_PROTECTED: dict[str, str] = {
    "c++":   "cpp",
    "c#":    "csharp",
    "f#":    "fsharp",
    ".net":  "dotnet",
}
# Compiled once
_PROTECTED_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(_PROTECTED, key=len, reverse=True))
)
# anything*.js  →  *js  (node.js→nodejs, next.js→nextjs)
_DOTJS_RE = re.compile(r"(\w+)\.js\b")
# URL pattern
_URL_RE = re.compile(r"https?://\S+")
# HN prefixes to strip
_HN_PREFIX_RE = re.compile(
    r"^(?:ask\s+hn|show\s+hn|tell\s+hn|launch\s+hn)\s*:\s*", re.IGNORECASE
)
# letter-run hyphen digit-run  →  single token  (gpt-4 → gpt4)
_HYPHEN_JOIN_RE = re.compile(r"([a-z]+)-(\d+)")
# non-alphanumeric (Unicode-aware: keeps letters and digits from any script)
_NON_ALNUM_RE = re.compile(r"[^\w\s]", re.UNICODE)
# collapse whitespace
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------
def clean_html(raw: str | None) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    # get_text with separator so tags don't glue words together
    text = soup.get_text(separator=" ")
    return _WS_RE.sub(" ", text).strip()


# ---------------------------------------------------------------------------
# URL → hostname
# ---------------------------------------------------------------------------
def _url_to_host(match: re.Match) -> str:
    host = urlparse(match.group(0)).hostname or ""
    return host.removeprefix("www.").replace(".", " ")


# ---------------------------------------------------------------------------
# Core tokenizer
# ---------------------------------------------------------------------------
def tokenize(text: str) -> list[str]:
    if not text:
        return []

    # 1. Unicode-normalize + lowercase
    text = unicodedata.normalize("NFKC", text).lower()

    # 2. Strip HN prefixes
    text = _HN_PREFIX_RE.sub("", text)

    # 3. Replace URLs with hostname
    text = _URL_RE.sub(_url_to_host, text)

    # 4. Protected substitutions
    text = _PROTECTED_RE.sub(lambda m: _PROTECTED[m.group(0)], text)
    text = _DOTJS_RE.sub(lambda m: m.group(1) + "js", text)

    # 5. Remove apostrophes (both ASCII and Unicode curly)
    text = text.replace("'", "").replace("\u2019", "")

    # 6a. Join letter-hyphen-digit runs
    text = _HYPHEN_JOIN_RE.sub(lambda m: m.group(1) + m.group(2), text)
    # 6b. Non-alphanumeric → space
    text = _NON_ALNUM_RE.sub(" ", text)

    # 7. Split, drop blanks and tokens > 30 chars
    tokens = [t for t in _WS_RE.sub(" ", text).split() if len(t) <= 30]

    # 8. Stopwords + conditional stemming (ASCII only, skip digit-containing)
    result = []
    for tok in tokens:
        if tok in _STOP_WORDS:
            continue
        if tok.isascii() and not any(c.isdigit() for c in tok):
            tok = _stem(tok)
        result.append(tok)

    return result


def preprocess_text(text: str) -> str:
    return " ".join(tokenize(text))


def preprocess_stories(stories: list) -> list:
    for story in stories:
        story["preprocessed_text"] = preprocess_text(story["text"])
    return stories
