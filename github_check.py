# github_check.py
import re
import requests

from ingest import CODE_EXTENSIONS, IGNORE_DIRS


def get_default_branch(owner: str, repo: str):
    """Fetch the repo's default branch name."""
    info = get_repo_info(owner, repo)
    return info["default_branch"]


def get_repo_tree(owner: str, repo: str, branch: str):
    """Fetch the full file tree for a branch, recursively, without cloning."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    if data.get("truncated"):
        print(
            "Warning: repo tree was truncated by GitHub's API (very large repo) — "
            "size estimate below may be incomplete."
        )

    return data["tree"]


def estimate_ingestible_size(repo_url: str):
    """
    More accurate check: walk the actual current file tree (not git history),
    and sum only the files we'd really ingest — same filters as ingest.py.
    """
    owner, repo = parse_github_url(repo_url)
    branch = get_default_branch(owner, repo)
    tree = get_repo_tree(owner, repo, branch)

    total_bytes = 0
    file_count = 0

    for entry in tree:
        if entry["type"] != "blob":
            continue
        path = entry["path"]

        # Skip anything inside an ignored directory
        if any(part in IGNORE_DIRS for part in path.split("/")):
            continue

        # Only count extensions we actually ingest
        if not any(path.endswith(ext) for ext in CODE_EXTENSIONS):
            continue

        total_bytes += entry.get("size", 0)
        file_count += 1

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "ingestible_files": file_count,
        "ingestible_kb": round(total_bytes / 1024, 2),
        "ingestible_mb": round(total_bytes / (1024 * 1024), 2),
    }


MAX_SIZE_KB = (
    15000  # ~15MB of repo content — reasonable ceiling for our free-tier LLM setup
)


def parse_github_url(url: str):
    """Extract owner/repo from a GitHub URL."""
    match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    if not match:
        raise ValueError(f"Could not parse GitHub URL: {url}")
    return match.group(1), match.group(2)


def get_repo_info(owner: str, repo: str):
    """Fetch repo metadata from GitHub's API — no cloning involved."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(url)
    if response.status_code == 404:
        raise ValueError(
            f"Repo not found: {owner}/{repo} (check it's public and spelled correctly)"
        )
    response.raise_for_status()
    return response.json()


def check_size_suitable(repo_url: str, max_size_kb: int = MAX_SIZE_KB):
    """
    Check if a public GitHub repo is a reasonable size to ingest,
    without cloning it.
    """
    owner, repo = parse_github_url(repo_url)
    info = get_repo_info(owner, repo)

    size_kb = info["size"]  # GitHub reports this in KB, based on the whole git history
    language = info.get("language", "unknown")
    stars = info.get("stargazers_count", 0)

    suitable = size_kb <= max_size_kb

    return {
        "owner": owner,
        "repo": repo,
        "size_kb": size_kb,
        "size_mb": round(size_kb / 1024, 2),
        "primary_language": language,
        "stars": stars,
        "suitable": suitable,
        "max_size_kb": max_size_kb,
    }


if __name__ == "__main__":
    import sys

    url = sys.argv[1]

    result = estimate_ingestible_size(url)
    MAX_MB = 15  # tune this based on testing

    print(f"Repo: {result['owner']}/{result['repo']} (branch: {result['branch']})")
    print(f"Ingestible files: {result['ingestible_files']}")
    print(f"Ingestible size: {result['ingestible_mb']} MB")
    print()
    if result["ingestible_mb"] <= MAX_MB:
        print(f"✅ Suitable for ingestion (under {MAX_MB} MB of actual code)")
    else:
        print(
            f"⚠️  Too large (over {MAX_MB} MB of actual code) — likely too many chunks for free-tier LLM limits"
        )
