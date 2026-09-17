from app.Services.prediction import IntentPredictionService
from app.Services.llm import LLMServices
from Rag.rag_service import RAGSerivce

class AssistantService:
    def __init__(self):
        self.prediction_service=(IntentPredictionService())
        self.llm_service=LLMServices()
        self.rag_service=RAGSerivce()

    def process(self, user_query, employee_id):
        prediction = self.prediction_service.predict(user_query)
        context = self.rag_service.get_context(
            user_query,
            top_k=3
        )
        prompt = f"""
You are an employee assistant.

Employee ID:
{employee_id}

User Query:
{user_query}

Detected Intent:
{prediction["intent"]}

Confidence:
{prediction["confidence"]}

Detected Entities:
{prediction["entities"]}

Company Knowledge Context:
{context}

Use employee tools when actual employee
information is required.

Use the company knowledge context when the
question is about company policies or general
company information.

Do not invent employee information.

Do not invent company policies.

Give a clear and natural response.
"""
        result=self.llm_service.genreate_response(prompt,context)
        return {
            "user_query": user_query,
            "intent": prediction["intent"],
            "confidence": prediction["confidence"],
            "entities": prediction["entities"],
            "response": result["response"],
            "tool_used": result.get("tool_used"),
            "tool_result": result.get("tool_result"),
            "rag_context": context
        }