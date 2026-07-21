# github_check.py
import re
import requests

MAX_SIZE_KB = 5000  # ~5MB of repo content — reasonable ceiling for our free-tier LLM setup


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
        raise ValueError(f"Repo not found: {owner}/{repo} (check it's public and spelled correctly)")
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
    result = check_size_suitable(url)

    print(f"Repo: {result['owner']}/{result['repo']}")
    print(f"Size: {result['size_mb']} MB")
    print(f"Primary language: {result['primary_language']}")
    print(f"Stars: {result['stars']}")
    print()
    if result["suitable"]:
        print(f"✅ Suitable for ingestion (under {result['max_size_kb'] / 1024} MB limit)")
    else:
        print(f"⚠️  Too large (over {result['max_size_kb'] / 1024} MB limit) — ingestion may be slow or produce too many chunks")