import tiktoken

from bulldogent.baseline.types import Chunk

_ENCODING = tiktoken.get_encoding("cl100k_base")

_DEFAULT_CHUNK_SIZE = 500  # tokens
_DEFAULT_OVERLAP = 50  # tokens


def chunk_text(
    text: str,
    source: str,
    title: str,
    url: str,
    metadata: dict[str, str] | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Split text into overlapping chunks respecting paragraph/sentence boundaries."""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current_tokens: list[int] = []

    for paragraph in paragraphs:
        paragraph_tokens = _ENCODING.encode(paragraph)

        if len(paragraph_tokens) > chunk_size:
            # Large paragraph — split by sentences
            if current_tokens:
                chunks.append(_make_chunk(current_tokens, source, title, url, metadata))
                current_tokens = _overlap_tokens(current_tokens, overlap)

            sentence_chunks = _split_sentences(paragraph, chunk_size, overlap)
            for sc in sentence_chunks:
                chunks.append(_make_chunk(sc, source, title, url, metadata))
            last = sentence_chunks[-1] if sentence_chunks else []
            current_tokens = _overlap_tokens(last, overlap)
            continue

        # Would exceed chunk_size — flush current buffer
        if current_tokens and len(current_tokens) + len(paragraph_tokens) > chunk_size:
            chunks.append(_make_chunk(current_tokens, source, title, url, metadata))
            current_tokens = _overlap_tokens(current_tokens, overlap)

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
