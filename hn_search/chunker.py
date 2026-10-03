"""
Chunking for semantic indexing.

Terminology
-----------
chunk_text  – the raw text stored in the DB (chunk body only)
embed_text  – what gets passed to the encoder: "title: <title>\\n\\n<chunk_text>"
              Keep this composition in one place (embed_text()).

Token budget
------------
all-MiniLM-L6-v2 uses BertTokenizer, max_len=256.
200 words/chunk body leaves ~39 tokens of headroom for title prefix +
subword splits of technical terms.  Verified empirically.
"""

import hashlib
import re
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from hn_search.models import Chunk

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
_CHUNK_WORDS = 160        # target body size (words); hard ceiling is 190
_CHUNK_MAX = 190          # hard word ceiling per chunk body
_OVERLAP = 35             # words carried from previous chunk
_MIN_WORDS = 30           # drop trailing chunks smaller than this
_MAX_CHUNKS = 20          # cap per story
_HEAD_ARTICLE_WORDS = 60  # article words included in chunk-0 head

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_PARA_RE = re.compile(r"\n{2,}")


# ---------------------------------------------------------------------------
# Public composition point
# ---------------------------------------------------------------------------
def embed_text(title: str, chunk_text: str) -> str:
    """Single place that defines what the encoder receives."""
    return f"{title}\n\n{chunk_text}"


# ---------------------------------------------------------------------------
# Internal splitters (no NLTK)
# ---------------------------------------------------------------------------
def _words(text: str) -> list[str]:
    return text.split()


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_paragraphs(text: str) -> list[str]:
    parts = _PARA_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _merge_to_chunks(units: list[str], target: int, hard_max: int) -> list[list[str]]:
    """
    Merge text units (paragraphs or sentences) into word-capped groups.
    Returns list of word lists.
    """
    groups: list[list[str]] = []
    current: list[str] = []

    for unit in units:
        unit_words = _words(unit)
        # Unit alone exceeds hard_max → hard-split by words
        if len(unit_words) > hard_max:
            if current:
                groups.append(current)
                current = []
            for i in range(0, len(unit_words), hard_max):
                groups.append(unit_words[i: i + hard_max])
            continue

        if len(current) + len(unit_words) > target and current:
            groups.append(current)
            current = list(unit_words)
        else:
            current.extend(unit_words)

    if current:
        groups.append(current)

    return groups


def _apply_overlap(groups: list[list[str]], overlap: int, hard_max: int) -> list[str]:
    """Prepend tail of previous group to each group, trim to hard_max, return joined strings."""
    result: list[str] = []
    for i, g in enumerate(groups):
        if i == 0:
            result.append(" ".join(g))
        else:
            tail = groups[i - 1][-overlap:]
            combined = tail + g
            result.append(" ".join(combined[:hard_max]))
    return result


# ---------------------------------------------------------------------------
# Core public function
# ---------------------------------------------------------------------------
def build_chunks(
    title: str,
    hn_text: str | None,
    article_text: str | None,
) -> list[str]:
    """
    Return an ordered list of chunk_text strings (body only, no title prefix).

    Chunk 0 is always the "head": title + HN text + first _HEAD_ARTICLE_WORDS
    words of the article, so title-style queries always hit something.

    Remaining chunks come from the article body with overlap.
    Stories with no article text get exactly one chunk.
    """
    title = (title or "").strip()
    hn = (hn_text or "").strip()
    article = (article_text or "").strip()

    # --- chunk 0: head ---
    head_parts = [p for p in [title, hn] if p]
    article_words = _words(article)
    if article_words:
        head_parts.append(" ".join(article_words[:_HEAD_ARTICLE_WORDS]))
    head = " ".join(head_parts)

    if not article_words or len(article_words) <= _HEAD_ARTICLE_WORDS:
        # Nothing left to chunk further
        return [head]

    # --- remaining article body ---
    body_words = article_words[_HEAD_ARTICLE_WORDS:]
    body = " ".join(body_words)

    # Split into paragraphs first, then sentences within oversized paragraphs
    paragraphs = _split_paragraphs(body)
    units: list[str] = []
    for para in paragraphs:
        if len(_words(para)) > _CHUNK_MAX:
            units.extend(_split_sentences(para))
        else:
            units.append(para)

    groups = _merge_to_chunks(units, _CHUNK_WORDS, _CHUNK_MAX)
    body_chunks = _apply_overlap(groups, _OVERLAP, _CHUNK_MAX)

    chunks = [head] + body_chunks

    # --- drop tiny trailing chunks (unless it's the only one) ---
    while len(chunks) > 1 and len(_words(chunks[-1])) < _MIN_WORDS:
        chunks.pop()

    # --- cap ---
    return chunks[:_MAX_CHUNKS]


# ---------------------------------------------------------------------------
# DB writer
# ---------------------------------------------------------------------------
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def save_chunks(
    db: AsyncSession,
    story_id: int,
    chunks: list[str],
) -> int:
    """
    Transactionally replace chunks for story_id only when content changed.
    Compares text_hash per chunk_index; unchanged chunks are left alone.
    Returns number of chunks written (0 = nothing changed).
    """
    new_hashes = [_sha256(c) for c in chunks]

    # Fetch existing hashes in index order
    rows = await db.execute(
        select(Chunk.chunk_index, Chunk.text_hash)
        .where(Chunk.story_id == story_id)
        .order_by(Chunk.chunk_index)
    )
    existing: dict[int, str | None] = {idx: h for idx, h in rows.all()}

    # Check if anything changed
    if (
        len(existing) == len(chunks)
        and all(existing.get(i) == new_hashes[i] for i in range(len(chunks)))
    ):
        return 0

    # Delete all existing chunks for this story and reinsert
    await db.execute(delete(Chunk).where(Chunk.story_id == story_id))

    rows_to_insert = [
        {
            "story_id": story_id,
            "chunk_index": i,
            "text": text,
            "text_hash": new_hashes[i],
        }
        for i, text in enumerate(chunks)
    ]
    await db.execute(pg_insert(Chunk).values(rows_to_insert))
    return len(chunks)
