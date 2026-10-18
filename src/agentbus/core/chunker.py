"""Heading-aware markdown chunker keeping code fences intact (FR-1, FR-3)."""

import re
from typing import List, Tuple

MAX_CHUNK_BYTES = 4096


def _split_oversized_text(text: str, max_bytes: int = MAX_CHUNK_BYTES) -> List[str]:
    """Split text exceeding max_bytes at blank lines, newlines, spaces, or hard byte slices."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return [text]

    # Try splitting by double newline (paragraphs)
    paragraphs = text.split("\n\n")
    if len(paragraphs) > 1:
        chunks = []
        current = []
        current_len = 0
        for p in paragraphs:
            p_len = len(p.encode("utf-8")) + 2
            if current and (current_len + p_len > max_bytes):
                sub = "\n\n".join(current)
                if len(sub.encode("utf-8")) > max_bytes:
                    chunks.extend(_split_oversized_text(sub, max_bytes))
                else:
                    chunks.append(sub)
                current = [p]
                current_len = p_len
            else:
                current.append(p)
                current_len += p_len
        if current:
            sub = "\n\n".join(current)
            if len(sub.encode("utf-8")) > max_bytes:
                chunks.extend(_split_oversized_text(sub, max_bytes))
            else:
                chunks.append(sub)
        return chunks

    # Try splitting by single newline
    lines = text.split("\n")
    if len(lines) > 1:
        chunks = []
        current = []
        current_len = 0
        for line in lines:
            line_len = len(line.encode("utf-8")) + 1
            if current and (current_len + line_len > max_bytes):
                sub = "\n".join(current)
                if len(sub.encode("utf-8")) > max_bytes:
                    chunks.extend(_split_oversized_text(sub, max_bytes))
                else:
                    chunks.append(sub)
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        if current:
            sub = "\n".join(current)
            if len(sub.encode("utf-8")) > max_bytes:
                chunks.extend(_split_oversized_text(sub, max_bytes))
            else:
                chunks.append(sub)
        return chunks

    # Safe fallback hard slice at max_bytes on valid UTF-8 boundary
    chunks = []
    start = 0
    while start < len(encoded):
        end = min(start + max_bytes, len(encoded))
        # Ensure we do not split in the middle of a multibyte UTF-8 sequence
        while end > start:
            try:
                chunk_str = encoded[start:end].decode("utf-8")
                break
            except UnicodeDecodeError:
                end -= 1
        if end == start:
            # Fallback if decode fails
            chunk_str = encoded[start:start + max_bytes].decode("utf-8", errors="ignore")
            end = start + max_bytes
        chunks.append(chunk_str)
        start = end

    return chunks


def chunk_markdown(content: str, max_bytes: int = MAX_CHUNK_BYTES) -> List[Tuple[str, str]]:
    """Split markdown text into (heading_path, body) chunks without breaking code blocks."""
    if not content or not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    chunks: List[Tuple[str, str]] = []

    current_headings: List[Tuple[int, str]] = []  # (level, title)
    current_body_lines: List[str] = []
    in_code_block = False

    atx_heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

    def get_current_heading_path() -> str:
        if not current_headings:
            return ""
        return " > ".join(title for _, title in current_headings)

    def flush_current_chunk():
        nonlocal current_body_lines
        if not current_body_lines:
            return
        body = "".join(current_body_lines).strip()
        if body:
            heading_path = get_current_heading_path()
            if len(body.encode("utf-8")) > max_bytes:
                sub_chunks = _split_oversized_text(body, max_bytes)
                for sub in sub_chunks:
                    if sub.strip():
                        chunks.append((heading_path, sub.strip()))
            else:
                chunks.append((heading_path, body))
        current_body_lines = []

    for line in lines:
        stripped = line.strip()

        # Track code fences
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            current_body_lines.append(line)
            continue

        if not in_code_block:
            heading_match = atx_heading_pattern.match(stripped)
            if heading_match:
                # Flush previous content under prior heading
                flush_current_chunk()

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Pop higher or equal level headings from stack
                while current_headings and current_headings[-1][0] >= level:
                    current_headings.pop()

                current_headings.append((level, title))
                continue

        current_body_lines.append(line)

    flush_current_chunk()

    # If document had no headings or empty chunks, return single fallback chunk
    if not chunks and content.strip():
        for sub in _split_oversized_text(content.strip(), max_bytes):
            chunks.append(("", sub))

    return chunks
