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

    def add_chunks(self, chunks: list[dict], batch_size: int = 100):
        """Embed and store chunks in batches."""
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = self.model.encode(texts, show_progress_bar=False).tolist()

            ids = [f"{c['filepath']}:{c['start_line']}-{c['end_line']}:{i+j}" for j, c in enumerate(batch)]
            metadatas = [
                {"filepath": c["filepath"], "start_line": c["start_line"], "end_line": c["end_line"]}
                for c in batch
            ]

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            print(f"  Embedded {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")

    def query(self, question: str, n_results: int = 5):
        """Semantic search: return top-N most relevant chunks for a question."""
        query_embedding = self.model.encode([question]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
        )
        return results

    def count(self):
        return self.collection.count()


def build_index(repo_path_or_url: str, db_path: str = DB_PATH):
    if repo_path_or_url.startswith("https://github.com"):
        from github_ingest import download_github_repo
        repo_path = download_github_repo(repo_path_or_url)
    else:
        repo_path = repo_path_or_url

    print(f"Ingesting: {repo_path}")
    chunks = ingest_repo(repo_path)
    print(f"Got {len(chunks)} chunks. Embedding and storing...")

    store = EmbedStore(db_path)
    store.add_chunks(chunks)

    # Record what's currently indexed
    with open(INDEX_META_PATH, "w") as f:
        json.dump({"source": repo_path_or_url}, f)

    print(f"Done. Collection now has {store.count()} chunks stored.")
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