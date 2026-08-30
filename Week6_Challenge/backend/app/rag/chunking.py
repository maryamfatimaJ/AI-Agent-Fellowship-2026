def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Character-based sliding window chunker. Simple and dependency-light; good enough
    for foundation-scale documents. Token-based chunking is a reasonable later upgrade.
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)

    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks
