from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model=SentenceTransformer("all-MiniLM-L6-v2")

def create_embedding(text):
    return model.encode(text)

def find_similarity(query,document):
    query_embedding=create_embedding(query)
    document_embedding=create_embedding(document)
    score=cosine_similarity([query_embedding],[document_embedding])[0][0]
    return score
if __name__ == "__main__":

    query = "How can I apply for leave?"
    query_embedding = create_embedding(query)
    documents = [
    "Employees should submit leave requests through the employee portal.",
    "Employees should complete check-in when they start work.",
    "Salary records contain basic salary, allowances and deductions."]
    for document in documents:
        document_embedding = create_embedding(document)
        score = cosine_similarity([query_embedding],[document_embedding])[0][0]
        print("\nDocument:")
        print(document)
        print("Score:", round(float(score), 4))