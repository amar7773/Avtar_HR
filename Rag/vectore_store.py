import chromadb

class VectorStore:
    def __init__(self):
        self.client=chromadb.PersistentClient(path="rag/chroma_db")
        self.collection=self.client.get_or_create_collection(name="company_knowledge")
    def add_documents(self,documents,embeddings):
        ids=[]
        texts=[]
        metadatas=[]
        for index,document in enumerate(documents):
            ids.append(str(index))
            texts.append(document["text"])
            metadatas.append({"source":document["source"]})
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas
            )
    def search(self,query_embedding,top_k=3):
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],n_results=top_k)
        return results