import os

# Prevent slow unauthenticated HuggingFace Hub checks on every model load
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from Rag.vectore_store import VectorStore


class RAGService:
    def __init__(self):
        self.model = None
        self.vector_store = VectorStore()

    def _get_model(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
        return self.model

    def retrieve(self, query, top_k=3):
        query_embedding = self._get_model().encode(query)
        results = self.vector_store.search(query_embedding, top_k=top_k)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {
                "text": doc,
                "source": metadatas[i]["source"],
                "distance": distances[i],
            }
            for i, doc in enumerate(documents)
        ]

    def get_context(self, query, top_k=3):
        results = self.retrieve(query, top_k)
        return "\n\n".join(result["text"] for result in results)