from sentence_transformers import SentenceTransformer

model=SentenceTransformer("all-MiniLM-L6-v2")

def create_embedding(text):
    embedding=model.encode(text)
    return embedding

if __name__=="__main__":
    query = "How can I apply for leave?"
    document = (
        "Employees should submit leave requests "
        "through the employee portal."
    )
    query_embedding=create_embedding(query)
    document_embedding=create_embedding(document)
    print("Query Vector Length:")
    print(len(query_embedding))

    print("\nDocument Vector Length:")
    print(len(document_embedding))