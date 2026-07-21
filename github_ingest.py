# github_ingest.py
import base64
import requests
from ingest import CODE_EXTENSIONS, IGNORE_DIRS, chunk_file
from github_check import parse_github_url, get_default_branch, get_repo_tree
import os
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
# GITHUB_TOKEN = None  # optionally set this, or load from .env — see note below


def _headers():
    if GITHUB_TOKEN:
        return {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    return {}


def fetch_blob_content(owner: str, repo: str, sha: str):
    """Fetch a single file's content by its blob SHA."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}"
    response = requests.get(url, headers=_headers())
    response.raise_for_status()
    data = response.json()

    if data.get("encoding") != "base64":
        return None  # unexpected encoding, skip

    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def ingest_github_repo(repo_url: str, max_files: int = 200):
    """
    Fetch and chunk a public GitHub repo's code, entirely via the API —
    no git clone involved. Mirrors ingest_repo()'s filtering and chunking.
    """
    owner, repo = parse_github_url(repo_url)
    branch = get_default_branch(owner, repo)
    tree = get_repo_tree(owner, repo, branch)

    # Apply the same filters as local ingestion
    relevant_entries = []
    for entry in tree:
        if entry["type"] != "blob":
            continue
        path = entry["path"]
        if any(part in IGNORE_DIRS for part in path.split("/")):
            continue
        if not any(path.endswith(ext) for ext in CODE_EXTENSIONS):
            continue
        relevant_entries.append(entry)

    if len(relevant_entries) > max_files:
        print(f"Warning: {len(relevant_entries)} files found, capping at {max_files} "
              f"to stay within API rate limits and reasonable index size.")
        relevant_entries = relevant_entries[:max_files]

    all_chunks = []
    for i, entry in enumerate(relevant_entries):
        content = fetch_blob_content(owner, repo, entry["sha"])
        if not content or not content.strip():
            continue
        chunks = chunk_file(entry["path"], content)
        all_chunks.extend(chunks)
        if (i + 1) % 20 == 0:
            print(f"  Fetched {i + 1}/{len(relevant_entries)} files...")

    print(f"Done. {len(all_chunks)} chunks from {len(relevant_entries)} files.")
    return all_chunks


if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    chunks = ingest_github_repo(url)
    if chunks:
        print("\nExample chunk:")
        print(f"File: {chunks[0]['filepath']} (lines {chunks[0]['start_line']}-{chunks[0]['end_line']})")
        print(chunks[0]['text'][:200])