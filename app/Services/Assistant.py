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

from app.Services.prediction import IntentPredictionService
from app.Services.llm import LLMServices, detect_language_mode
from app.Services.structured_query import StructuredQueryRouter
from Rag.rag_service import RAGSerivce
from Voice.Stt import STTService
from Voice.Tts import TTSService
import re
from uuid import uuid4
from Avtar.DID_Servicee import DIDService
from Avtar.avtar_config import get_avatar


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

        self.avatar = get_avatar()


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
                "rag_context": None
            }

        # 3. Intent prediction and RAG context retrieval
        prediction = self.prediction_service.predict(
            user_query
        )

        context = self.rag_service.get_context(
            user_query,
            top_k=3
        )

        result = self.llm_service.genreate_response(
            user_query,
            context,
            employee_id=employee_id,
            user_query=user_query,
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
            "hello", "hi", "hey", "hola", "namaste", "नमस्ते", "pranam", "प्रणाम",
            "ok", "okay", "theek hai", "thik hai", "theek", "thik", "ठीक", "ठीक है",
            "yes", "yeah", "yep", "haan", "ha", "हाँ",
            "no", "nope", "nah", "nahi", "nahin", "नहीं",
            "good morning", "good evening", "good afternoon", "shubh prabhat", "शुभ प्रभात",
            "how are you", "kaise ho", "kya haal hai", "kaisa chal raha hai", "आप कैसे हैं",
            "thank you", "thanks", "dhanyawad", "shukriya", "धन्यवाद", "शुक्रिया",
            "bye", "goodbye", "alvida", "अलvida", "see you"
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
                "language": "English",
                "intent": None,
                "confidence": 0,
                "response": "Sorry, I could not understand your voice input.",
                "tool_used": None,
                "tool_result": None,
                "rag_context": None,
                "error": str(e)
            }

    def process_text_to_speech(self, user_query, employee_id):
        result = self.process(user_query=user_query, employee_id=employee_id)
        response = result.get("response", "").strip()
        if not response:
            raise ValueError("No response generated.")
        resp_file = self.voice_dir / f"resp_{uuid4().hex[:8]}.mp3"
        audio_file = self.tts_service.generate_speech(
            text=response,
            output_file=str(resp_file)
        )
        result["audio_file"] = audio_file
        return result

    def _cleanup_old_voice_files(self, keep: int = 15):
        """Keep the latest response audio files to prevent unlimited disk growth."""
        try:
            files = sorted(
                self.voice_dir.glob("resp_*.mp3"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for f in files[keep:]:
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass

    def process_speech_to_speech(
        self,
        audio_file,
        employee_id,
        mode="avatar_mode"
    ):
        stt_lang = getattr(self.stt_service, "last_detected_language", None)
        try:
            user_text = self.stt_service.transcribe(audio_file)
        except Exception as stt_err:
            print(f"[STT RETRY]: {stt_err}")
            stt_lang = getattr(self.stt_service, "last_detected_language", None)
            if stt_lang in ("hin", "hi"):
                response_text = "आपकी आवाज़ ठीक से सुनाई नहीं दी, कृपया दोबारा बोलें।"
                detected_lang = "Hindi"
            elif stt_lang in ("eng", "en"):
                response_text = "I could not hear your voice clearly, please speak again."
                detected_lang = "English"
            else:
                response_text = "Aapki aawaz theek se sunayi nahi di, kripya dobara bolein."
                detected_lang = "Hinglish"

            resp_file = self.voice_dir / f"resp_{uuid4().hex[:8]}.mp3"
            response_audio = self.tts_service.generate_speech(
                text=response_text,
                output_file=str(resp_file)
            )
            avatar_info = {
                "talk_id": None,
                "status": "idle",
                "video_url": None,
            }
            if mode == "avatar_mode":
                import threading

                def _bg_talk_fallback():
                    try:
                        self.start_avatar(response_audio)
                    except Exception:
                        pass

                threading.Thread(target=_bg_talk_fallback, daemon=True).start()
                avatar_info = {
                    "talk_id": "latest",
                    "status": "instant",
                    "video_url": "/avatar-files/response_avatar.mp4",
                }

            return {
                "mode": mode,
                "language": detected_lang,
                "user_query": "",
                "response": response_text,
                "input_audio": audio_file,
                "response_audio": response_audio,
                "avatar": avatar_info,
            }

        if not user_text or not user_text.strip():
            if stt_lang in ("hin", "hi"):
                response_text = "आपकी आवाज़ ठीक से सुनाई नहीं दी, कृपया दोबारा बोलें।"
                detected_lang = "Hindi"
            elif stt_lang in ("eng", "en"):
                response_text = "I could not hear your voice clearly, please speak again."
                detected_lang = "English"
            else:
                response_text = "Aapki aawaz theek se sunayi nahi di, kripya dobara bolein."
                detected_lang = "Hinglish"

            resp_file = self.voice_dir / f"resp_{uuid4().hex[:8]}.mp3"
            response_audio = self.tts_service.generate_speech(
                text=response_text,
                output_file=str(resp_file)
            )

            avatar_info = {
                "talk_id": None,
                "status": "idle",
                "video_url": None,
            }
            if mode == "avatar_mode":
                import threading

                def _bg_talk_fallback2():
                    try:
                        self.start_avatar(response_audio)
                    except Exception:
                        pass

                threading.Thread(target=_bg_talk_fallback2, daemon=True).start()
                avatar_info = {
                    "talk_id": "latest",
                    "status": "instant",
                    "video_url": "/avatar-files/response_avatar.mp4",
                }

            return {
                "mode": mode,
                "language": detected_lang,
                "user_query": "",
                "response": response_text,
                "input_audio": audio_file,
                "response_audio": response_audio,
                "avatar": avatar_info,
            }

        result = self.process(user_query=user_text.strip(), employee_id=employee_id)
        detected_lang = result.get("language") or detect_language_mode(user_text.strip(), hint=stt_lang)
        result["language"] = detected_lang

        response_text = (result.get("response") or "").strip()
        if not response_text:
            if detected_lang == "Hindi":
                response_text = "मैं आपका अनुरोध समझ नहीं पाया, कृपया दोबारा पूछें।"
            elif detected_lang == "Hinglish":
                response_text = "Main aapka request samajh nahi paya, kripya dobara poochein."
            else:
                response_text = "I couldn't process your request, please ask again."
        result["response"] = response_text

        resp_file = self.voice_dir / f"resp_{uuid4().hex[:8]}.mp3"
        response_audio = self.tts_service.generate_speech(
            text=response_text,
            output_file=str(resp_file)
        )
        self._cleanup_old_voice_files()

        result["mode"] = mode
        result["input_audio"] = audio_file
        result["response_audio"] = response_audio

        if mode == "avatar_mode":
            print(f"Avatar input audio: {response_audio}")
            import threading

            def _bg_talk():
                try:
                    res = self.start_avatar(response_audio)
                    talk_id = res.get("talk_id")
                    self._latest_avatar_status = {
                        "talk_id": talk_id,
                        "status": "processing",
                        "video_url": None,
                    }
                except Exception as error:
                    print(f"[AVATAR ERROR] Background D-ID talk creation failed: {error}")
                    self._latest_avatar_status = {
                        "talk_id": None,
                        "status": "error",
                        "video_url": None,
                        "error": str(error),
                    }

            threading.Thread(target=_bg_talk, daemon=True).start()

            result["avatar"] = {
                "talk_id": "latest",
                "status": "instant",
                "video_url": "/avatar-files/response_avatar.mp4",
            }
        else:
            result["avatar"] = {
                "talk_id": None,
                "status": "idle",
                "video_url": None,
            }

        return result

    def get_current_avatar(self):
        try:
            return get_avatar()
        except Exception:
            return self.avatar

    def start_avatar(self, audio_file):
        print(f"Avatar input audio: {audio_file}")
        current_avatar = self.get_current_avatar()
        image_url = current_avatar.get("image_url")
        if not image_url:
            raise ValueError("No avatar image_url configured for D-ID.")

        did_service = DIDService()
        talk_info = did_service.start_talking_avatar_from_audio(
            image_url=image_url,
            audio_path=audio_file,
        )
        return {
            "audio_file": audio_file,
            "talk_id": talk_info["talk_id"],
            "audio_url": talk_info["audio_url"],
            "status": "processing",
            "video_url": None,
        }

    def generate_avatar(self, audio_file):
        did_service = DIDService()
        current_avatar = self.get_current_avatar()
        avatar_result = did_service.generate_avatar_from_audio(
            image_url=current_avatar.get("image_url", self.avatar.get("image_url")),
            audio_path=audio_file,
        )
        return {
            "audio_file": audio_file,
            "talk_id": avatar_result["talk_id"],
            "audio_url": avatar_result["audio_url"],
            "video_url": avatar_result.get("video_url"),
        }