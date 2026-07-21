# agent.py
import os
import json
from dotenv import load_dotenv
from groq import Groq

from embed_store import EmbedStore, build_index, INDEX_META_PATH
from tools import semantic_search, read_file, list_directory, grep_search

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.1-8b-instant"

# Tool schemas the model uses to decide what to call
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Search the codebase by meaning/concept. Use this first for most questions — e.g. 'how is authentication handled', 'where are sockets set up'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a specific file. Use when semantic_search found a relevant snippet but you need the complete file for full context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path relative to repo root, e.g. 'server.ts'"},
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders at a given path in the repo. Use to understand project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subpath": {"type": "string", "description": "Path relative to repo root, default '.' for root"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for an exact string or regex pattern across all code files. Use when you need exact matches, e.g. a function name or variable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Exact string or regex to search for"},
                },
                "required": ["pattern"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a codebase assistant. You have tools to explore a real codebase: \
semantic search, reading full files, listing directories, and exact-match grep search.

You MUST use the proper tool-calling mechanism to invoke tools — never write a tool call as plain text \
in your response. Only call tools that are defined in the tools list provided to you.

CRITICAL: When you call a tool using information from a previous tool's result (like a filepath found \
via grep_search or semantic_search), you MUST copy the exact value from that result. Never invent, \
guess, or use a placeholder path like 'path/to/file.ts' — only use paths you have actually seen in a \
tool result.

Use tools as needed — you may call several in sequence to gather enough context before answering. \
Always ground your answer in what the tools actually returned; do not guess at code you haven't seen. \
Cite file paths and line numbers when relevant. If you're not confident after searching, say so."""


def _get_indexed_source():
    try:
        with open(INDEX_META_PATH) as f:
            return json.load(f).get("source")
    except FileNotFoundError:
        return None


class Agent:
    def __init__(self, repo_path_or_url: str, status_callback=None):
        self.is_github = repo_path_or_url.startswith("https://github.com")
        self.store = EmbedStore()

        indexed_source = _get_indexed_source()
        needs_rebuild = self.store.count() == 0 or indexed_source != repo_path_or_url

        if needs_rebuild:
            if self.store.count() > 0:
                self.store.client.delete_collection(self.store.collection.name)
            self.store, self.repo_path = build_index(repo_path_or_url, status_callback=status_callback)
        elif self.is_github:
            from github_ingest import download_github_repo
            if status_callback:
                status_callback(10, "Re-downloading repo files for this session...")

            def download_progress(current, total):
                pct = int((current / total) * 90) if total else 10
                if status_callback:
                    status_callback(10 + pct // 10, f"Downloading source files ({current} of {total})...")

            self.repo_path = download_github_repo(repo_path_or_url, progress_callback=download_progress)
            if status_callback:
                status_callback(100, "Index ready.")
        else:
            self.repo_path = repo_path_or_url
            if status_callback:
                status_callback(100, "Index ready.")

    def _call_tool(self, name: str, args: dict):
        if name == "semantic_search":
            return semantic_search(self.store, args["query"])
        elif name == "read_file":
            return read_file(self.repo_path, args["filepath"])
        elif name == "list_directory":
            return list_directory(self.repo_path, args.get("subpath", "."))
        elif name == "grep_search":
            return grep_search(self.repo_path, args["pattern"])
        else:
            return f"Unknown tool: {name}"

    def ask(self, question: str, max_turns: int = 5):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        for turn in range(max_turns):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                # Model is done — this is the final answer
                return msg.content

            # Model wants to call one or more tools
            messages.append(msg)
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments) or {}
                print(f"  [tool call] {fn_name}({fn_args})")

                result = self._call_tool(fn_name, fn_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })

        return "Reached max tool-call turns without a final answer."


if __name__ == "__main__":
    import sys
    repo = sys.argv[1]
    agent = Agent(repo)

    print("Codebase agent ready. Type a question (or 'exit').\n")
    while True:
        question = input("> ")
        if question.strip().lower() in ("exit", "quit"):
            break
        answer = agent.ask(question)
        print(f"\n{answer}\n")