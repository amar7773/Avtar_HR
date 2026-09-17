from app.Services.prediction import IntentPredictionService
from app.Services.llm import LLMServices

class AssistantService:
    def __init__(self):
        self.prediction_service=(IntentPredictionService())
        self.llm_service=LLMServices()

    def process(self, user_query, employee_id):
        prediction = self.prediction_service.predict(user_query)
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

Use the available tools when actual employee
information is required.

Do not invent employee information.

Give a clear and natural response.
"""
        result=self.llm_service.genreate_response(prompt)
        return {
            "user_query": user_query,
            "intent": prediction["intent"],
            "confidence": prediction["confidence"],
            "entities": prediction["entities"],
            "response": result["response"],
            "tool_used": result.get("tool_used"),
            "tool_result": result.get("tool_result")
          }