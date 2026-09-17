from sentence_transformers import SentenceTransformer
from Rag.vectore_store import VectorStore

model = SentenceTransformer("all-MiniLM-L6-v2")

documents = [

    {
        "text": (
            "Employees should submit leave requests "
            "through the employee portal."),
        "source": "leave_policy.txt"
    },

    {
        "text": (
            "Employees should check their available "
            "leave balance before submitting a request."),
        "source": "leave_policy.txt"
    },
    {
        "text": (
            "Expense claims should include the "
            "required bill or receipt."),
        "source": "expense_policy.txt"
    },
    {
        "text": (
            "Employees should complete check-in when "
            "they start work and check-out when they finish work."
        ),
        "source": "attendance_policy.txt"
    },
    {
        "text": (
            "Salary records may contain basic salary, "
            "allowances, deductions and net salary."
        ),
        "source": "salary_policy.txt"
    }
]
texts=[
    document["text"]
    for document in documents
]
embeddings=model.encode(texts)
vector_store = VectorStore()
vector_store.add_documents(
    documents,
    embeddings
)
print("Documents added to vector database successfully.")