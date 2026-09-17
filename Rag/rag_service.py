from sentence_transformers import SentenceTransformer
from Rag.vectore_store import VectorStore

class RAGSerivce:
    def __init__(self):
        self.model=SentenceTransformer("all-MiniLM-L6-v2")
        self.vectore_store=VectorStore()
    def retrive(self,query,top_k=3):
        query_embedding=self.model.encode(query)
        results=self.vectore_store.search(
            query_embedding,
            top_k=top_k
        )
        retrieved_documents = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i,document in enumerate(documents):
            retrieved_documents.append({
                "text":document,
                "source":metadatas[i]["source"],
                "distance":distances[i]
            })
        return retrieved_documents
    def get_context(self,query,top_k=3):
        results=self.retrive(
            query,top_k
        )
        context="\n\n".join(result["text"] for result in results)
        return context
if __name__=="__main__":
    rag=RAGSerivce()
    query = "How can I apply for leave?"
    results = rag.retrive(
        query,
        top_k=3
    )
    print("\nQuery:")
    print(query)
    print("\nRetrieved Results:")
    for i, result in enumerate(
        results,
        start=1
    ):
        print(f"\n--- Result {i} ---")
        print("Source:", result["source"])
        print("Distance:", result["distance"])
        print("Text:", result["text"])
    print("\n========== CONTEXT ==========")
    context = rag.get_context(
        query,
        top_k=3
    )
    print(context)