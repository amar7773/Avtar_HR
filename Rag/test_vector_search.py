from sentence_transformers import SentenceTransformer
from Rag.vectore_store import VectorStore

model=SentenceTransformer("all-MiniLM-L6-v2")
vectore_store=VectorStore()
query = "How can I apply for leave?"
query_embedding=model.encode(query)
results=vectore_store.search(query_embedding,top_k=3)
print("\nQuery:")
print(query)
print("\nRelevant Documents:")

for i, document in enumerate(
    results["documents"][0],
    start=1
):
    print(f"\n--- Result {i} ---")

    print("Document:")
    print(document)
    print(
        "Source:",
        results["metadatas"][0][i - 1]["source"]
    )