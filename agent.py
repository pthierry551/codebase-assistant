# agent.py
import os
import json
from dotenv import load_dotenv
from groq import Groq

from embed_store import EmbedStore
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


class Agent:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.store = EmbedStore()

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