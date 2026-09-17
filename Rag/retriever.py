from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class Retriver:
    def __init__(self):
        self.model=SentenceTransformer("all-MiniLM-L6-v2")
        self.documents=[
            {
                "text": "Employees should submit leave requests through the employee portal.",
                "source": "leave_policy.txt"
            },
            {
                "text": "Employees should check their available leave balance before submitting a request.",
                "source": "leave_policy.txt"
            },
            {
                "text": "The manager may approve or reject a leave request based on company requirements.",
                "source": "leave_policy.txt"
            },
            {
                "text": "Employees can submit eligible business expenses through the employee portal.",
                "source": "expense_policy.txt"
            },
            {
                "text": "Expense claims should include the required bill or receipt.",
                "source": "expense_policy.txt"
            },
            {
                "text": "Employees should complete check-in when they start work and check-out when they finish work.",
                "source": "attendance_policy.txt"
            },
            {
                "text": "Salary records may contain basic salary, allowances, deductions and net salary.",
                "source": "salary_policy.txt"
            }
        ]
        self.embedding=self.model.encode([document["text"] for document in self.documents])
    def retrive(self,query,top_k=3):
        query_embedding=self.model.encode([query])
        scores=cosine_similarity(query_embedding,self.embedding)[0]
        results=[]
        for index,score in enumerate(scores):
            results.append({
                "text":self.documents[index]["text"],
                "source":self.documents[index]["source"],
                "score":float(score)
            })
        results.sort(key=lambda x:x["score"],reverse=True)
        return results[:top_k]
if __name__ == "__main__":

    retriever = Retriver()
    query = "What document is required for expense reimbursement?"
    results = retriever.retrive(
        query,
        top_k=3
    )
    print("\nQuery:")
    print(query)
    print("\nTop Results:")
    for i, result in enumerate(results, start=1):
        print(f"\n--- Result {i} ---")
        print("Source:", result["source"])
        print("Score:", round(result["score"], 4))
        print("Text:", result["text"])