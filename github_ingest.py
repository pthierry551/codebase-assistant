import os
import base64
import tempfile
import shutil
import requests
from pathlib import Path
from ingest import CODE_EXTENSIONS, IGNORE_DIRS
from github_check import parse_github_url, get_default_branch, get_repo_tree

GITHUB_TOKEN = None


def _headers():
    if GITHUB_TOKEN:
        return {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    return {}


def cleanup_old_github_temp_dirs():
    """Remove any leftover github_* temp folders from previous sessions."""
    temp_root = Path(tempfile.gettempdir())
    removed = 0
    for folder in temp_root.glob("github_*"):
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    if removed:
        print(f"Cleaned up {removed} leftover temp folder(s) from previous sessions.")


def fetch_blob_content(owner: str, repo: str, sha: str):
    """Fetch a single file's content by its blob SHA."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}"
    response = requests.get(url, headers=_headers())
    response.raise_for_status()
    data = response.json()

    if data.get("encoding") != "base64":
        return None

    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def download_github_repo(repo_url: str, max_files: int = 200) -> str:
    """
    Fetch a public GitHub repo's relevant files via the API and write them
    into a fresh temp folder on disk. Cleans up leftover folders from
    previous sessions first.
    """
    cleanup_old_github_temp_dirs()

    owner, repo = parse_github_url(repo_url)
    branch = get_default_branch(owner, repo)
    tree = get_repo_tree(owner, repo, branch)

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
        print(f"Warning: {len(relevant_entries)} files found, capping at {max_files}.")
        relevant_entries = relevant_entries[:max_files]

    temp_dir = tempfile.mkdtemp(prefix=f"github_{owner}_{repo}_")
    print(f"Downloading into temp folder: {temp_dir}")

    written = 0
    for i, entry in enumerate(relevant_entries):
        content = fetch_blob_content(owner, repo, entry["sha"])
        if not content or not content.strip():
            continue

        dest_path = Path(temp_dir) / entry["path"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")
        written += 1

        if (i + 1) % 20 == 0:
            print(f"  Fetched {i + 1}/{len(relevant_entries)} files...")

    print(f"Done. {written} files written to {temp_dir}")
    return temp_dir


if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    local_path = download_github_repo(url)
    print(f"\nRepo available locally at: {local_path}")