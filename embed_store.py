# embed_store.py
import json
import chromadb
from sentence_transformers import SentenceTransformer
from ingest import ingest_repo

# Small, fast, good-quality embedding model — runs locally, no API cost
MODEL_NAME = "all-MiniLM-L6-v2"

COLLECTION_NAME = "codebase_chunks"
DB_PATH = "./chroma_db"
INDEX_META_PATH = "./chroma_db_meta.json"

class EmbedStore:
    def __init__(self, db_path: str = DB_PATH):
        self.model = SentenceTransformer(MODEL_NAME)
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(COLLECTION_NAME)

    def add_chunks(self, chunks: list[dict], batch_size: int = 100, progress_callback=None):
        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = self.model.encode(texts, show_progress_bar=False).tolist()

            ids = [f"{c['filepath']}:{c['start_line']}-{c['end_line']}:{i+j}" for j, c in enumerate(batch)]
            metadatas = [
                {"filepath": c["filepath"], "start_line": c["start_line"], "end_line": c["end_line"]}
                for c in batch
            ]

            self.collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

            if progress_callback:
                progress_callback(min(i + batch_size, total), total)

    def query(self, question: str, n_results: int = 3):
        query_embedding = self.model.encode([question]).tolist()
        return self.collection.query(query_embeddings=query_embedding, n_results=n_results)

    def count(self):
        return self.collection.count()


def build_index(repo_path_or_url: str, db_path: str = DB_PATH, status_callback=None):
    """
    status_callback(percent: int, message: str) is called throughout, so a UI
    can show live progress + a human-readable explanation of the current step.
    """
    def report(pct, message):
        if status_callback:
            status_callback(pct, message)

    if repo_path_or_url.startswith("https://github.com"):
        report(0, "Checking the GitHub repo and preparing to download its files...")
        from github_ingest import download_github_repo

        def download_progress(current, total):
            pct = int((current / total) * 40) if total else 0
            report(pct, f"Downloading source files from GitHub ({current} of {total})...")

        repo_path = download_github_repo(repo_path_or_url, progress_callback=download_progress)
    else:
        repo_path = repo_path_or_url
        report(5, "Reading files from the local folder...")

    report(45, "Scanning files and splitting them into searchable chunks...")
    chunks = ingest_repo(repo_path)

    report(50, f"Found {len(chunks)} code sections. Loading the embedding model...")
    store = EmbedStore(db_path)

    def embed_progress(current, total):
        pct = 50 + int((current / total) * 50) if total else 50
        report(pct, f"Building the search index ({current} of {total} chunks)...")

    store.add_chunks(chunks, progress_callback=embed_progress)

    with open(INDEX_META_PATH, "w") as f:
        json.dump({"source": repo_path_or_url}, f)

    report(100, "Index ready.")
    return store, repo_path


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    store = build_index(repo)

    # quick sanity test
    test_question = "how is authentication handled"
    print(f"\nTest query: '{test_question}'")
    results = store.query(test_question, n_results=3)
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        print(f"\n--- {meta['filepath']} (lines {meta['start_line']}-{meta['end_line']}) ---")
        print(doc[:150])