from app.Services.llm import LLMServices
from Rag.rag_service import RAGSerivce

llm=LLMServices()
rag=RAGSerivce()
query = "What is the company policy for work from home?"
context = rag.get_context(
    query,
    top_k=3
)
print("\n========== RETRIEVED CONTEXT ==========")
print(context)
response = llm.genreate_response(
    query,
    context
)
print("\n========== FINAL ANSWER ==========")
print(response)