# 🔍 Codebase Assistant

A RAG + agentic AI tool that answers questions about a real codebase — not just by retrieving similar text, but by deciding for itself which tools to use: semantic search, reading full files, listing directories, or exact-match grep search.

Built to explore how retrieval-augmented generation and agentic tool-use work together, using entirely free tools (Groq's free-tier LLM, local embeddings, local vector storage).

## Why this is more than "just RAG"

Most RAG demos do one thing: embed a question, retrieve similar chunks, stuff them into a prompt. This project goes a step further — the LLM is given a set of tools and decides, per question, what it actually needs:

- A vague conceptual question → semantic search
- "Where exactly is `X` used?" → exact grep search
- "Show me the whole function" → read the full file
- "What's in this folder?" → list directory contents

The agent can chain these together. For example, asking *"find where `roomName` is defined and show me the complete function"* triggers:

```
[tool call] grep_search({'pattern': 'roomName'})
[tool call] read_file({'filepath': 'server.ts'})
```

It searches first, sees the real file path in the result, and only then reads that exact file — rather than guessing or hallucinating a path.

## Works on local folders *or* public GitHub repos

Point it at a local folder, or hand it a public GitHub URL directly — no `git clone` required:

```bash
python agent.py https://github.com/kennethreitz/requests
```

Under the hood, this:
1. Checks the repo's actual ingestible size via GitHub's Trees API (no cloning) and warns if it's too large for a free-tier LLM's context/rate limits
2. Fetches only relevant source files via the GitHub API and writes them into a temp folder, preserving the real relative paths
3. Reuses the exact same ingestion → embedding → agent pipeline as a local folder
4. Automatically detects if the target repo changed since the last run and rebuilds the index — otherwise it reuses the existing one
5. Cleans up leftover temp folders from previous sessions automatically

## How it works

```
Local folder  or  GitHub URL
      │                │
      │         github_check.py   estimates ingestible size via the
      │                │           Trees API, no cloning
      │                ▼
      │         github_ingest.py  fetches relevant files via the API,
      │                │           writes them into a temp folder
      │                │
      └────────┬───────┘
               ▼
 ingest.py        walks the repo, filters out build artifacts/minified code,
                   chunks files into overlapping segments
      │
      ▼
 embed_store.py    embeds chunks locally (sentence-transformers) and stores
                   them in a local ChromaDB vector database
      │
      ▼
 tools.py          exposes 4 tools: semantic_search, read_file,
                   list_directory, grep_search
      │
      ▼
 agent.py          runs a tool-calling loop via Groq's free-tier LLM —
                   the model decides which tools to call, observes results,
                   and either calls more tools or gives a final answer
      │
      ▼
 app.py            Streamlit chat UI for asking questions in the browser
```

## Tech stack (100% free)

| Component | Tool | Why |
|---|---|---|
| LLM + tool-calling | [Groq](https://console.groq.com) (`llama-3.1-8b-instant`) | Free tier, fast inference, reliable function-calling |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Runs fully locally, no API cost |
| Vector store | ChromaDB | Local, persistent, free |
| GitHub access | [GitHub REST API](https://docs.github.com/en/rest) | Fetch public repo files with no cloning required |
| UI | Streamlit | Free hosting on Streamlit Community Cloud |

## Setup

```bash
git clone https://github.com/pthierry551/codebase-assistant.git
cd codebase-assistant
pip install -r requirements.txt
```

Create a `.env` file:

```
GROQ_API_KEY=gsk_your_key_here
GITHUB_TOKEN=ghp_your_token_here
```

- Get a free Groq key at [console.groq.com](https://console.groq.com).
- The GitHub token is optional but strongly recommended — unauthenticated GitHub API calls are limited to 60 requests/hour, versus 5,000/hour with a token. Create one at [github.com/settings/tokens](https://github.com/settings/tokens) → "Generate new token (classic)" → no scopes needed for public repos.

## Usage

**Check if a public GitHub repo is a suitable size before ingesting (no cloning):**

```bash
python github_check.py https://github.com/pallets/flask
```

**Index a repo** (local folder or GitHub URL):

```bash
python embed_store.py /path/to/your/repo
python embed_store.py https://github.com/kennethreitz/requests
```

**Chat via terminal** (local folder or GitHub URL — auto-builds the index on first run):

```bash
python agent.py /path/to/your/repo
python agent.py https://github.com/kennethreitz/requests
```

**Chat via browser UI:**

```bash
streamlit run app.py
```

## Demo

![demo](demo.gif)

## What I'd build next

- Swap line-based chunking for AST-aware chunking (split by function/class boundaries, not fixed line counts) for more coherent retrieval
- GitHub URL support in the Streamlit UI (currently CLI-only)
- Show the agent's tool-call steps live in the Streamlit UI, not just the final answer
- Optional local-only mode via Ollama, for zero external API dependency
- More precise GitHub size estimation using per-file blob sizes for repos GitHub's Trees API truncates

## License

MIT
