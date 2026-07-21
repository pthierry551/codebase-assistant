# file_tree.py
from pathlib import Path
from ingest import walk_repo


def build_file_tree(repo_path: str) -> dict:
    """Nested dict representing the ingestible folder/file structure."""
    tree = {}
    for filepath, _ in walk_repo(repo_path):
        parts = Path(filepath).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("__files__", []).append(parts[-1])
    return tree


def render_tree_html(tree: dict, depth: int = 0) -> str:
    """Render the nested dict as a collapsible HTML tree (uses <details>/<summary>)."""
    html = ""
    folders = {k: v for k, v in tree.items() if k != "__files__"}
    files = sorted(tree.get("__files__", []))

    for name, subtree in sorted(folders.items()):
        open_attr = "open" if depth == 0 else ""
        html += (
            f'<details class="tree-node" {open_attr}>'
            f'<summary>📁 {name}</summary>'
            f'{render_tree_html(subtree, depth + 1)}'
            f'</details>'
        )
    for name in files:
        html += f'<div class="tree-file">📄 {name}</div>'

    return html