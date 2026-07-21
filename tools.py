# tools.py
import os
import re
from pathlib import Path
from embed_store import EmbedStore

# Reuse the same ignore rules as ingestion so list_directory/grep stay clean
from ingest import IGNORE_DIRS, CODE_EXTENSIONS


def semantic_search(store: EmbedStore, query: str, n_results: int = 5):
    """Search the codebase by meaning, not exact text."""
    results = store.query(query, n_results=n_results)
    output = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        output.append({
            "filepath": meta["filepath"],
            "lines": f"{meta['start_line']}-{meta['end_line']}",
            "content": doc,
        })
    return output


def read_file(repo_path: str, filepath: str):
    """Read a full file's contents given its relative path."""
    full_path = Path(repo_path) / filepath
    try:
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(repo_path: str, subpath: str = "."):
    """List files and folders under a given path in the repo."""
    target = Path(repo_path) / subpath
    if not target.exists():
        return f"Path not found: {subpath}"
    entries = []
    for item in sorted(target.iterdir()):
        if item.name in IGNORE_DIRS:
            continue
        entries.append(f"{'[DIR] ' if item.is_dir() else ''}{item.name}")
    return "\n".join(entries)


def grep_search(repo_path: str, pattern: str, max_matches: int = 20):
    """Search for an exact string/regex across the codebase."""
    repo_path = Path(repo_path)
    matches = []
    regex = re.compile(pattern)

    for path in repo_path.rglob("*"):
        if path.is_dir() or path.suffix not in CODE_EXTENSIONS:
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines):
            if regex.search(line):
                matches.append(f"{path.relative_to(repo_path)}:{i+1}: {line.strip()}")
                if len(matches) >= max_matches:
                    return "\n".join(matches)
    return "\n".join(matches) if matches else "No matches found."


if __name__ == "__main__":
    import sys
    from embed_store import EmbedStore

    repo = sys.argv[1]
    store = EmbedStore()

    print("=== list_directory ===")
    print(list_directory(repo))

    print("\n=== grep_search 'roomName' ===")
    print(grep_search(repo, "roomName"))