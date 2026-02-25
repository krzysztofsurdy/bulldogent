import tiktoken

from bulldogent.baseline.types import Chunk

_ENCODING = tiktoken.get_encoding("cl100k_base")


class Chunker:
    """Splits text into overlapping token-based chunks."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk_text(
        self,
        text: str,
        source: str,
        title: str,
        url: str,
        metadata: dict[str, str] | None = None,
    ) -> list[Chunk]:
        """Split text into overlapping chunks respecting paragraph/sentence boundaries."""
        if not text.strip():
            return []

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[Chunk] = []
        current_tokens: list[int] = []

        for paragraph in paragraphs:
            paragraph_tokens = _ENCODING.encode(paragraph)

            if len(paragraph_tokens) > self._chunk_size:
                # Large paragraph — split by sentences
                if current_tokens:
                    chunks.append(_make_chunk(current_tokens, source, title, url, metadata))
                    current_tokens = _overlap_tokens(current_tokens, self._overlap)

                sentence_chunks = _split_sentences(paragraph, self._chunk_size, self._overlap)
                for sc in sentence_chunks:
                    chunks.append(_make_chunk(sc, source, title, url, metadata))
                last = sentence_chunks[-1] if sentence_chunks else []
                current_tokens = _overlap_tokens(last, self._overlap)
                continue

            # Would exceed chunk_size — flush current buffer
            if current_tokens and len(current_tokens) + len(paragraph_tokens) > self._chunk_size:
                chunks.append(_make_chunk(current_tokens, source, title, url, metadata))
                current_tokens = _overlap_tokens(current_tokens, self._overlap)

            current_tokens.extend(paragraph_tokens)

        if current_tokens:
            chunks.append(_make_chunk(current_tokens, source, title, url, metadata))

        return chunks


def _split_sentences(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[list[int]]:
    """Split a long paragraph into token chunks at sentence boundaries."""
    # Simple sentence splitting: period/question/exclamation followed by space
    sentences: list[str] = []
    current = ""
    for char in text:
        current += char
        if char in ".!?" and len(current.strip()) > 1:
            sentences.append(current)
            current = ""
    if current.strip():
        sentences.append(current)

    chunks: list[list[int]] = []
    current_tokens: list[int] = []

    for sentence in sentences:
        sentence_tokens = _ENCODING.encode(sentence)

        if current_tokens and len(current_tokens) + len(sentence_tokens) > chunk_size:
            chunks.append(current_tokens)
            current_tokens = _overlap_tokens(current_tokens, overlap)

        current_tokens.extend(sentence_tokens)

    if current_tokens:
        chunks.append(current_tokens)

    return chunks


def _overlap_tokens(tokens: list[int], overlap: int) -> list[int]:
    """Return the last `overlap` tokens for continuity with the next chunk."""
    if overlap <= 0 or not tokens:
        return []
    return tokens[-overlap:]


def _make_chunk(
    tokens: list[int],
    source: str,
    title: str,
    url: str,
    metadata: dict[str, str] | None,
) -> Chunk:
    return Chunk(
        content=_ENCODING.decode(tokens),
        source=source,
        title=title,
        url=url,
        metadata=metadata or {},
    )


def count_tokens(text: str) -> int:
    """Count tokens using the cl100k_base encoding."""
    return len(_ENCODING.encode(text))
