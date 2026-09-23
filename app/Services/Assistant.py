from app.Services.prediction import IntentPredictionService
from app.Services.llm import LLMServices
from Rag.rag_service import RAGSerivce
from Voice.Stt import STTService
from Voice.Tts import TTSService
from Avtar.DID_Servicee import DIDService
from Avtar.avtar_config import get_avatar

class AssistantService:
    def __init__(self):
        self.prediction_service=(IntentPredictionService())
        self.llm_service=LLMServices()
        self.rag_service=RAGSerivce()
        self.stt_service=STTService()
        self.tts_service=TTSService()
        self.avatar = get_avatar()

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
    def process_voice(self, audio_file, employee_id):
        try:
            text = self.stt_service.transcribe(audio_file)
            result = self.process(user_query=text,employee_id=employee_id)
            result["audio_file"] = audio_file
            return result
        except Exception as e:
            return {
            "user_query": "",
            "intent": None,
            "confidence": 0,
            "response": "Sorry, I could not understand your voice input.",
            "tool_used": None,
            "tool_result": None,
            "rag_context": None,
            "error": str(e)
            }
    def process_text_to_speech(self,user_query,employee_id):
        result=self.process(user_query=user_query,employee_id=employee_id)
        audio_file=self.tts_service.generate_speech(text=result["response"],
            output_file="Voice/ai_response.mp3")
        result["audio_file"] = audio_file
        return result
    def process_speech_to_speech(self,audio_file,employee_id):
        user_text=self.stt_service.transcribe(audio_file)
        result=self.process(user_query=user_text,employee_id=employee_id)
        response_audio = self.tts_service.generate_speech(
        text=result["response"],
        output_file="Voice/ai_response.mp3")
        result["input_audio"] = audio_file
        result["response_audio"] = response_audio
        return result

    def generate_avatar(self, text):
        did_service = DIDService()
        audio_file = self.tts_service.generate_speech(
            text=text,
            output_file="Voice/avatar_response.mp3",
        )
        avatar_result = did_service.generate_avatar_from_audio(
            image_url=self.avatar["image_url"],
            audio_path=audio_file,
        )
        return {
            "audio_file": audio_file,
            "talk_id": avatar_result["talk_id"],
            "audio_url": avatar_result["audio_url"],
        }