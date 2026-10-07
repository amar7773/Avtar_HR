import sys
from pathlib import Path

# Ensure Windows terminal doesn't crash on Devanagari or Unicode prints
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import re
import threading

from app.Services.prediction import IntentPredictionService
from app.Services.llm import LLMServices, detect_language_mode
from app.Services.structured_query import StructuredQueryRouter
from Rag.rag_service import RAGService
from Voice.Stt import STTService
from Voice.Tts import TTSService
from Voice.response_audio_lock import lock_response_audio
from Avtar.DID_Servicee import DIDService
from Avtar.avtar_config import get_avatar


class AssistantService:

    def __init__(self):
        self.voice_dir = Path(__file__).resolve().parents[2] / "Voice"
        self.response_audio_path = self.voice_dir / "ai_response.mp3"
        self._audio_pipeline_lock = threading.Lock()

        self.prediction_service = IntentPredictionService()
        self.llm_service = LLMServices()
        self.structured_router = StructuredQueryRouter()
        self.rag_service = RAGService()
        self.stt_service = STTService()
        self.tts_service = TTSService()

        self._conversation_history = {}

    def process(self, user_query, employee_id):
        history = self._conversation_history.get(str(employee_id), [])
        lang_mode = detect_language_mode(user_query)

        # 1. Near-instant small-talk handling (no RAG, no ML model inference needed)
        if self._is_small_talk(user_query):
            response = self.llm_service.generate_small_talk_response(
                user_query=user_query,
                employee_id=employee_id,
                conversation_history=history,
                lang_mode=lang_mode,
            )
            self._remember(employee_id, user_query, response)
            return {
                "user_query": user_query,
                "language": lang_mode,
                "intent": "small_talk",
                "confidence": 1.0,
                "entities": {},
                "response": response,
                "tool_used": None,
                "tool_result": None,
                "rag_context": None,
            }

        # 2. Fast deterministic structured queries for employee data (no RAG needed)
        structured = self.structured_router.route(
            user_query, employee_id, conversation_history=history
        )
        if structured is not None:
            response = self.llm_service.generate_structured_response(
                user_query=user_query,
                employee_id=employee_id,
                result=structured,
                conversation_history=history,
                lang_mode=lang_mode,
            )
            self._remember(employee_id, user_query, response)
            return {
                "user_query": user_query,
                "language": lang_mode,
                "intent": structured.get("intent", "employee_data"),
                "confidence": 1.0,
                "entities": structured.get("entities", {}),
                "response": response,
                "tool_used": structured.get("tool_used"),
                "tool_result": structured,
                "rag_context": None,
            }

        # 3. Intent prediction and RAG context retrieval
        prediction = self.prediction_service.predict(user_query)
        context = self.rag_service.get_context(user_query, top_k=3)

        result = self.llm_service.generate_response(
            query=user_query,
            context=context,
            employee_id=employee_id,
            conversation_history=history,
            lang_mode=lang_mode,
        )
        self._remember(employee_id, user_query, result["response"])

        return {
            "user_query": user_query,
            "language": lang_mode,
            "intent": prediction["intent"],
            "confidence": prediction["confidence"],
            "entities": prediction["entities"],
            "response": result["response"],
            "tool_used": result.get("tool_used"),
            "tool_result": result.get("tool_result"),
            "rag_context": context,
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
            "hello", "hi", "hey", "hola", "namaste", "नमस्ते", "pranam", "प्रणाम",
            "ok", "okay", "theek hai", "thik hai", "theek", "thik", "ठीक", "ठीक है",
            "yes", "yeah", "yep", "haan", "ha", "हाँ",
            "no", "nope", "nah", "nahi", "nahin", "नहीं",
            "good morning", "good evening", "good afternoon", "shubh prabhat", "शुभ प्रभात",
            "how are you", "kaise ho", "kya haal hai", "kaisa chal raha hai", "आप कैसे हैं",
            "thank you", "thanks", "dhanyawad", "shukriya", "धन्यवाद", "शुक्रिया",
            "bye", "goodbye", "alvida", "अलvida", "see you",
        }
        return normalized in tokens

    def process_speech_to_speech(
        self, audio_file, employee_id, mode="avatar_mode", stream_id=None, session_id=None
    ):
        try:
            user_text = self.stt_service.transcribe(audio_file)
        except Exception as error:
            raise RuntimeError(f"Speech transcription failed: {error}") from error

        if not user_text or not user_text.strip():
            raise ValueError("Speech transcription returned no text; no avatar talk was created.")

        stt_lang = getattr(self.stt_service, "last_detected_language", None)
        result = self.process(user_query=user_text.strip(), employee_id=employee_id)

        detected_lang = result.get("language") or detect_language_mode(user_text.strip(), hint=stt_lang)
        result["language"] = detected_lang

        response_text = (result.get("response") or "").strip()
        if not response_text:
            raise ValueError("The AI assistant returned an empty response; no avatar talk was created.")
        result["response"] = response_text

        with self._audio_pipeline_lock, lock_response_audio(self.response_audio_path):
            response_audio = self.tts_service.generate_speech(
                text=response_text,
                output_file=str(self.response_audio_path),
            )
            avatar_info = {"talk_id": None, "status": "idle", "video_url": None}
            if mode == "avatar_mode":
                if stream_id and session_id:
                    try:
                        avatar_info = self.talk_stream_avatar(
                            stream_id=stream_id,
                            session_id=session_id,
                            audio_file=response_audio,
                            response_text=response_text,
                        )
                    except Exception as err:
                        print(f"[STREAM TALK INFO] WebRTC stream talk failed: {err}; using standard avatar fallback.")
                        avatar_info = self.start_avatar(response_audio, response_text)
                else:
                    avatar_info = self.start_avatar(response_audio, response_text)

        result["mode"] = mode
        result["input_audio"] = audio_file
        result["response_audio"] = response_audio
        result["avatar"] = avatar_info
        return result

    def process_text(
        self, user_query, employee_id, mode="text_mode", stream_id=None, session_id=None
    ):
        result = self.process(user_query=user_query, employee_id=employee_id)
        response_text = (result.get("response") or "").strip()
        result["response"] = response_text
        result["mode"] = mode

        if mode == "avatar_mode":
            with self._audio_pipeline_lock, lock_response_audio(self.response_audio_path):
                response_audio = self.tts_service.generate_speech(
                    text=response_text,
                    output_file=str(self.response_audio_path),
                )
                if stream_id and session_id:
                    try:
                        avatar_info = self.talk_stream_avatar(
                            stream_id=stream_id,
                            session_id=session_id,
                            audio_file=response_audio,
                            response_text=response_text,
                        )
                    except Exception as err:
                        print(f"[STREAM TALK INFO] WebRTC stream talk failed: {err}; using standard avatar fallback.")
                        avatar_info = self.start_avatar(response_audio, response_text)
                else:
                    avatar_info = self.start_avatar(response_audio, response_text)
            result["response_audio"] = response_audio
            result["avatar"] = avatar_info
        else:
            result["avatar"] = {"talk_id": None, "status": "idle", "video_url": None}

        return result

    def talk_stream_avatar(self, stream_id, session_id, audio_file, response_text):
        audio_path = Path(audio_file).resolve()
        if audio_path != self.response_audio_path.resolve():
            raise ValueError("Avatar streaming must use Voice/ai_response.mp3.")
        self.tts_service.validate_generated_speech(response_text, audio_path)
        did_service = DIDService()
        expression = did_service.expression_for_response(response_text)
        res = did_service.talk_stream_from_audio(
            stream_id=stream_id,
            session_id=session_id,
            audio_path=str(audio_path),
            expression=expression,
        )
        return {
            "stream_id": stream_id,
            "session_id": session_id,
            "status": "speaking",
            "is_stream": True,
            "expression": expression,
            "data": res,
        }

    def start_avatar(self, audio_file, response_text):
        audio_path = Path(audio_file).resolve()
        if audio_path != self.response_audio_path.resolve():
            raise ValueError("Avatar generation must use Voice/ai_response.mp3.")
        audio_hash = self.tts_service.validate_generated_speech(
            response_text,
            audio_path,
        )
        current_avatar = get_avatar()
        image_url = current_avatar.get("image_url")
        if not image_url:
            raise ValueError("No avatar image_url configured for D-ID.")

        try:
            did_service = DIDService()
            talk_info = did_service.start_talking_avatar_from_audio(
                image_url=image_url,
                audio_path=str(self.response_audio_path),
                expression=did_service.expression_for_response(response_text),
            )
            if talk_info.get("audio_sha256") != audio_hash:
                raise RuntimeError("D-ID uploaded audio differs from the current response MP3.")
            return {
                "audio_file": str(self.response_audio_path),
                "talk_id": talk_info["talk_id"],
                "audio_url": talk_info["audio_url"],
                "audio_sha256": audio_hash,
                "status": "processing",
                "video_url": None,
            }
        except Exception as error:
            error_str = str(error)
            print(f"[AVATAR WARNING] D-ID talk creation error: {error_str}")
            is_credit = "credit" in error_str.lower()
            return {
                "audio_file": str(self.response_audio_path),
                "talk_id": None,
                "audio_url": None,
                "audio_sha256": audio_hash,
                "status": "error",
                "error": "Insufficient D-ID credits" if is_credit else error_str,
                "credit_exhausted": is_credit,
                "video_url": None,
            }