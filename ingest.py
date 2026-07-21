# ingest.py
import os
from pathlib import Path

# File types we care about for a code assistant
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".md"}

# Directories to skip
IGNORE_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}


def walk_repo(repo_path: str):
    """Yield (filepath, content) for every relevant file in the repo."""
    repo_path = Path(repo_path)
    for path in repo_path.rglob("*"):
        if path.is_dir():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.suffix not in CODE_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if content.strip():
            yield str(path.relative_to(repo_path)), content


def chunk_file(filepath: str, content: str, max_lines: int = 60):
    """
    Split a file into chunks. Simple line-based chunking for now,
    with overlap so context isn't lost at boundaries.
    We'll upgrade to AST-based function/class splitting in a later step.
    """
    lines = content.splitlines()
    chunks = []
    overlap = 10
    step = max_lines - overlap

    for i in range(0, len(lines), step):
        chunk_lines = lines[i : i + max_lines]
        if not chunk_lines:
            continue
        chunk_text = "\n".join(chunk_lines)
        chunks.append(
            {
                "filepath": filepath,
                "start_line": i + 1,
                "end_line": i + len(chunk_lines),
                "text": chunk_text,
            }
        )
    return chunks


def ingest_repo(repo_path: str):
    """Full ingestion: walk repo, chunk every file, return list of chunks."""
    all_chunks = []
    for filepath, content in walk_repo(repo_path):
        chunks = chunk_file(filepath, content)
        all_chunks.extend(chunks)
    return all_chunks


if __name__ == "__main__":
    import sys

    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    chunks = ingest_repo(repo)
    print(f"Ingested {len(chunks)} chunks from {repo}")
    if chunks:
        print("\nExample chunk:")
        print(
            f"File: {chunks[0]['filepath']} (lines {chunks[0]['start_line']}-{chunks[0]['end_line']})"
        )
        print(chunks[0]["text"][:200])
