"""Split policy wording into clause-sized chunks for retrieval."""

import re
from dataclasses import dataclass

# Headings such as "SECTION I", "Section 2 - Exclusions", "A. Dwelling", "4.2 Water damage", "EXCLUSIONS"
_HEADING = re.compile(
    r"^(?:(?:section|part|article)\s+[ivx\d]+\b.*"
    r"|[A-Z]\.\s+\S.*"
    r"|\d+(?:\.\d+)*\.?\s+[A-Z].*"
    r"|[A-Z][A-Z \-&/]{3,})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Chunk:
    clause_id: str
    content: str


def _slug(heading: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", heading.upper()).strip("-")[:40] or "CLAUSE"


def chunk_policy(text: str, prefix: str, max_words: int = 400, overlap_words: int = 40) -> list[Chunk]:
    """Split on headings; break long sections into overlapping windows. Clause IDs are stable per document."""
    sections: list[tuple[str, list[str]]] = [("PREAMBLE", [])]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADING.match(stripped) and len(stripped.split()) <= 12:
            sections.append((stripped, []))
        else:
            sections[-1][1].append(stripped)

    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    for heading, lines in sections:
        words = " ".join(lines).split()
        if not words:
            continue
        base = f"{prefix}-{_slug(heading)}"
        step = max_words - overlap_words
        for start in range(0, len(words), step):
            window = words[start : start + max_words]
            seen[base] = seen.get(base, 0) + 1
            clause_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
            chunks.append(Chunk(clause_id=clause_id, content=f"{heading}\n{' '.join(window)}"))
            if start + max_words >= len(words):
                break
    return chunks
