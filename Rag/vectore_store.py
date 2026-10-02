import chromadb
from pathlib import Path


# Resolve the chroma_db path relative to this file's location
_CHROMA_DB_PATH = str(Path(__file__).resolve().parent / "chroma_db")


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=_CHROMA_DB_PATH)
        self.collection = self.client.get_or_create_collection(name="company_knowledge")

    def add_documents(self, documents, embeddings):
        ids = []
        texts = []
        metadatas = []

        for index, document in enumerate(documents):
            ids.append(str(index))
            texts.append(document["text"])
            metadatas.append({"source": document["source"]})

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )

    def search(self, query_embedding, top_k=3):
        return self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
        )