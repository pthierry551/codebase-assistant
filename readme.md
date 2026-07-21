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

## How it works

```
Local codebase
      │
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
```

Get a free key at [console.groq.com](https://console.groq.com).

## Usage

**Index a repo:**

```bash
python embed_store.py /path/to/your/repo
```

**Chat via terminal:**

```bash
python agent.py /path/to/your/repo
```

**Chat via browser UI:**

```bash
streamlit run app.py
```

## Demo

![demo](demo.gif)

## What I'd build next

- Swap line-based chunking for AST-aware chunking (split by function/class boundaries, not fixed line counts) for more coherent retrieval
- Multi-repo support with a repo picker in the UI
- Show the agent's tool-call steps live in the Streamlit UI, not just the final answer
- Optional local-only mode via Ollama, for zero external API dependency

## License

MIT
