from pathlib import Path

from app.Services.prediction import IntentPredictionService
from app.Services.llm import LLMServices
from app.Services.structured_query import StructuredQueryRouter
from Rag.rag_service import RAGSerivce
from Voice.Stt import STTService
from Voice.Tts import TTSService
import re
# from Avtar.DID_Servicee import DIDService
# from Avtar.avtar_config import get_avatar


class AssistantService:

    def __init__(self):

        self.voice_dir = Path(__file__).resolve().parents[2] / "Voice"

        self.prediction_service = IntentPredictionService()

        self.llm_service = LLMServices()
        self.structured_router = StructuredQueryRouter()

        self.rag_service = RAGSerivce()

        self.stt_service = STTService()

        self.tts_service = TTSService()
        self._conversation_history = {}

        # self.avatar = get_avatar()


    def process(self, user_query, employee_id):
        history = self._conversation_history.get(str(employee_id), [])

        prediction = self.prediction_service.predict(
            user_query
        )

        if self._is_small_talk(user_query):
            response = self.llm_service.generate_small_talk_response(
                user_query=user_query,
                employee_id=employee_id,
                conversation_history=history,
            )
            self._remember(employee_id, user_query, response)
            return {
                "user_query": user_query,
                "intent": prediction["intent"],
                "confidence": prediction["confidence"],
                "entities": prediction["entities"],
                "response": response,
                "tool_used": None,
                "tool_result": None,
                "rag_context": None,
            }

        # Resolve supported employee data deterministically before retrieval or
        # generation. This keeps exact values out of the model's guess space.
        structured = self.structured_router.route(user_query, employee_id)
        if structured is not None:
            response = self.llm_service.generate_structured_response(
                user_query=user_query,
                employee_id=employee_id,
                result=structured
            )
            self._remember(employee_id, user_query, response)
            return {
                "user_query": user_query,
                "intent": prediction["intent"],
                "confidence": prediction["confidence"],
                "entities": prediction["entities"],
                "response": response,
                "tool_used": structured.get("tool_used"),
                "tool_result": structured,
                "rag_context": None
            }

        context = self.rag_service.get_context(
            user_query,
            top_k=3
        )

        prompt = f"""
You are an AI Employee Assistant.

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

IMPORTANT:

1. Use employee tools when actual employee information
   is required.

2. The employee ID for this request is:
   {employee_id}

3. Do not ask the employee to provide their employee ID
   when it is already provided by the application.

4. Use RAG/company context for company policies and
   general company information.

5. Do not invent employee data.

6. Do not invent company policies.

7. Do not expose MongoDB IDs or internal database fields.

8. Give a clear, natural and concise response.

9. If the question is a normal general-knowledge question and is not
   about employee or company data, answer it directly using your general
   knowledge. Do not require employee tools or company context for it.
"""

        result = self.llm_service.genreate_response(
            user_query,
            context,
            employee_id=employee_id,
            user_query=user_query,
            conversation_history=history,
        )
        self._remember(employee_id, user_query, result["response"])

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

    def _remember(self, employee_id, user_query, response):
        history = self._conversation_history.setdefault(str(employee_id), [])
        history.extend([
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": response},
        ])
        del history[:-12]

    @staticmethod
    def _is_small_talk(user_query):
        normalized = re.sub(r"[.!?,]+", "", user_query.casefold())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = {
            "hello", "hi", "hey", "hola", "namaste", "नमस्ते",
            "ok", "okay", "ठीक", "ठीक है", "yes", "yeah", "yep",
            "haan", "हाँ", "no", "nope", "nah", "nahi", "नहीं",
        }
        return normalized in tokens


    def process_voice(self, audio_file, employee_id):

        try:

            text = self.stt_service.transcribe(
                audio_file
            )

            result = self.process(
                user_query=text,
                employee_id=employee_id
            )

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


    def process_text_to_speech(
        self,
        user_query,
        employee_id
    ):

        result = self.process(
            user_query=user_query,
            employee_id=employee_id,
            conversation_history=history,
        )
        self._remember(employee_id, user_query, response)

        audio_file = self.tts_service.generate_speech(
            text=result["response"],
            output_file=str(self.voice_dir / "ai_response.mp3")
        )

        result["audio_file"] = audio_file

        return result


    def process_speech_to_speech(
        self,
        audio_file,
        employee_id
    ):

        user_text = self.stt_service.transcribe(
            audio_file
        )

        if not user_text or not user_text.strip():
            raise ValueError(
                "No speech was detected in the uploaded audio."
            )

        result = self.process(
            user_query=user_text.strip(),
            employee_id=employee_id
        )

        response_text = (result.get("response") or "").strip()
        if not response_text:
            response_text = (
                "I could not generate a response for that request. "
                "Please try again."
            )
            result["response"] = response_text

        response_audio = self.tts_service.generate_speech(
            text=response_text,
            output_file=str(self.voice_dir / "ai_response.mp3")
        )

        result["input_audio"] = audio_file

        result["response_audio"] = response_audio

        return result


    # def generate_avatar(self, text):

    #     did_service = DIDService()

    #     audio_file = self.tts_service.generate_speech(
    #         text=text,
    #         output_file="Voice/avatar_response.mp3",
    #     )

    #     avatar_result = did_service.generate_avatar_from_audio(
    #         image_url=self.avatar["image_url"],
    #         audio_path=audio_file,
    #     )

    #     return {
    #         "audio_file": audio_file,
    #         "talk_id": avatar_result["talk_id"],
    #         "audio_url": avatar_result["audio_url"],
    #     }