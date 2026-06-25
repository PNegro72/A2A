"""
Structured-based chunker.

Why structured chunking?
  Fixed-size / sliding-window approaches ignore document semantics: they may
  cut in the middle of a sentence, separate a table header from its rows, or
  split a code block arbitrarily.  Structured chunking first PARSES the document
  into semantic elements (headings, paragraphs, tables, lists, code blocks),
  then GROUPS them under their parent heading, and finally SPLITS or MERGES
  groups so each chunk stays within the target size while preserving coherence.

Algorithm (3 phases):
  1. Parse  → detect element type + indentation level for every block of text.
  2. Group  → accumulate elements under the current section header until the
              group would exceed CHUNK_SIZE; then emit it as a chunk.
  3. Overlap → copy the last CHUNK_OVERLAP characters from the previous chunk
               as a leading context prefix for the next chunk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_CHUNK_SIZE
from src.loaders import RawPage


# ─────────────────────────────────────────────
#  Output model
# ─────────────────────────────────────────────

@dataclass
class Chunk:
    """A single chunk ready for embedding and storage."""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)


# ─────────────────────────────────────────────
#  Element types
# ─────────────────────────────────────────────

_HEADING_RE = re.compile(
    r"^(#{1,6})\s+(.+)"          # Markdown headings  ## Title
    r"|^([A-Z][^\n]{0,120})\n[-=]{3,}",  # Setext headings
    re.MULTILINE,
)

_TABLE_BLOCK_RE = re.compile(
    r"\[TABLE\](.*?)\[/TABLE\]",
    re.DOTALL,
)

_CODE_BLOCK_RE = re.compile(
    r"```[\s\S]*?```|~~~[\s\S]*?~~~",
)

_BULLET_RE = re.compile(r"^[\s]*[-*•]\s+", re.MULTILINE)


@dataclass
class _Element:
    kind: str          # heading | paragraph | table | list | code | other
    level: int         # heading depth (1-6), 0 for non-headings
    text: str


# ─────────────────────────────────────────────
#  Parser
# ─────────────────────────────────────────────

def _parse_elements(text: str) -> list[_Element]:
    """
    Split raw text into typed structural elements.

    Strategy:
      - Extract code blocks and tables first (they must not be split further).
      - Split remainder on blank lines.
      - Classify each block as heading / list / paragraph / other.
    """
    elements: list[_Element] = []

    # Protect code blocks and tables with placeholders
    placeholders: dict[str, str] = {}

    def _protect(m: re.Match) -> str:
        key = f"\x00BLOCK{len(placeholders)}\x00"
        placeholders[key] = m.group(0)
        return key

    text = _CODE_BLOCK_RE.sub(_protect, text)
    text = _TABLE_BLOCK_RE.sub(_protect, text)

    # Split on 1+ blank lines
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Restore placeholder
        if block in placeholders:
            raw = placeholders[block]
            kind = "table" if "[TABLE]" in raw else "code"
            elements.append(_Element(kind=kind, level=0, text=raw))
            continue

        # Check heading
        m = re.match(r"^(#{1,6})\s+(.+)", block)
        if m:
            level = len(m.group(1))
            elements.append(_Element(kind="heading", level=level, text=block))
            continue

        # Check list
        if _BULLET_RE.search(block):
            elements.append(_Element(kind="list", level=0, text=block))
            continue

        # Default: paragraph
        elements.append(_Element(kind="paragraph", level=0, text=block))

    return elements


# ─────────────────────────────────────────────
#  Sentence-aware splitter (fallback for oversized paragraphs)
# ─────────────────────────────────────────────

_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def _split_by_sentences(text: str, max_size: int) -> list[str]:
    """
    Recursively split text at sentence boundaries until each piece ≤ max_size.
    Falls back to hard split if a single sentence exceeds max_size.
    """
    if len(text) <= max_size:
        return [text]

    sentences = _SENTENCE_END_RE.split(text)
    pieces: list[str] = []
    current = ""

    for sent in sentences:
        if not sent.strip():
            continue
        if len(current) + len(sent) + 1 <= max_size:
            current = (current + " " + sent).strip()
        else:
            if current:
                pieces.append(current)
            # Sentence itself too large → hard split
            if len(sent) > max_size:
                for start in range(0, len(sent), max_size):
                    pieces.append(sent[start: start + max_size])
                current = ""
            else:
                current = sent

    if current:
        pieces.append(current)

    return pieces if pieces else [text[:max_size]]


# ─────────────────────────────────────────────
#  Grouping & chunk assembly
# ─────────────────────────────────────────────

def _build_chunks(
    elements: list[_Element],
    chunk_size: int,
    overlap: int,
    base_metadata: dict[str, Any],
) -> list[Chunk]:
    """
    Walk through the element list, accumulating a running group.
    When a group would exceed chunk_size, flush it and start fresh.
    Overlap is implemented by prepending the tail of the previous chunk.
    """
    chunks: list[Chunk] = []
    section_path: list[str] = []   # breadcrumb of current headings
    current_parts: list[str] = []
    current_len = 0
    chunk_index = 0
    prev_tail = ""                  # last CHUNK_OVERLAP chars of previous chunk

    def _flush() -> None:
        nonlocal current_parts, current_len, chunk_index, prev_tail

        text = "\n\n".join(current_parts).strip()
        if len(text) < MIN_CHUNK_SIZE:
            current_parts = []
            current_len = 0
            return

        # Prepend overlap context
        full_text = (prev_tail + "\n\n" + text).strip() if prev_tail else text
        prev_tail = text[-overlap:] if len(text) > overlap else text

        section_label = " > ".join(section_path) if section_path else ""
        meta = {
            **base_metadata,
            "chunk_index":  chunk_index,
            "section":      section_label,
            "char_count":   len(full_text),
        }
        chunks.append(Chunk(text=full_text, metadata=meta))
        chunk_index += 1
        current_parts = []
        current_len = 0

    for elem in elements:
        # Update section breadcrumb on heading
        if elem.kind == "heading":
            # Flush pending content before new section
            if current_parts:
                _flush()
            # Trim deeper headings from path
            while len(section_path) >= elem.level:
                if section_path:
                    section_path.pop()
                else:
                    break
            section_path.append(elem.text.lstrip("#").strip())
            # Include heading text in the next chunk for context
            current_parts.append(elem.text)
            current_len += len(elem.text)
            continue

        # Tables and code blocks are emitted as standalone chunks (never split)
        if elem.kind in ("table", "code"):
            if current_parts:
                _flush()
            if len(elem.text) >= MIN_CHUNK_SIZE:
                section_label = " > ".join(section_path) if section_path else ""
                chunks.append(Chunk(
                    text=elem.text,
                    metadata={
                        **base_metadata,
                        "chunk_index": chunk_index,
                        "section":     section_label,
                        "kind":        elem.kind,
                        "char_count":  len(elem.text),
                    },
                ))
                chunk_index += 1
            continue

        # Regular content: paragraph / list / other
        # If the single element is too large, split it first
        sub_pieces = (
            _split_by_sentences(elem.text, chunk_size)
            if len(elem.text) > chunk_size
            else [elem.text]
        )

        for piece in sub_pieces:
            if current_len + len(piece) > chunk_size and current_parts:
                _flush()
            current_parts.append(piece)
            current_len += len(piece)

    # Flush any remaining content
    if current_parts:
        _flush()

    return chunks


# ─────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────

def chunk_pages(
    pages: list[RawPage],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Convert a list of RawPage objects into Chunk objects.

    Each page is parsed and chunked, but the tail of the last chunk from the
    previous page is prepended to the current page's text. This cross-page
    overlap ensures content that spans a page boundary (e.g. a list split
    across two PDF pages) ends up in at least one contiguous chunk.
    """
    all_chunks: list[Chunk] = []
    prev_page_tail: str = ""

    for page in pages:
        page_text = (prev_page_tail + "\n\n" + page.text).strip() if prev_page_tail else page.text
        elements = _parse_elements(page_text)
        page_chunks = _build_chunks(
            elements=elements,
            chunk_size=chunk_size,
            overlap=overlap,
            base_metadata={**page.metadata},
        )
        for chunk in page_chunks:
            chunk.metadata["page"] = page.metadata.get("page", 1)

        if page_chunks:
            prev_page_tail = page_chunks[-1].text[-overlap:]

        all_chunks.extend(page_chunks)

    # Re-number chunk_index globally across all pages
    for i, chunk in enumerate(all_chunks):
        chunk.metadata["chunk_index"] = i

    return all_chunks
