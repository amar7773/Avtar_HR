import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.Services.llm import LLMServices
from Rag.rag_service import RAGService


def test_rag_llm():
    llm = LLMServices()
    rag = RAGService()
    query = "What is the company policy for work from home?"
    context = rag.get_context(query, top_k=3)
    assert context is not None
    response = llm.generate_response(query=query, context=context)
    assert response is not None
    assert "response" in response


if __name__ == "__main__":
    test_rag_llm()