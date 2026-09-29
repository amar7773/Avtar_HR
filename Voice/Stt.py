import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

# Ensure Windows terminal doesn't crash on Devanagari or Unicode characters
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


class STTService:

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "Configuration error: 'ELEVENLABS_API_KEY' is missing from the environment or .env file."
            )

        # Official ElevenLabs Scribe STT model
        self.model_id = os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v1")
        self.client = ElevenLabs(api_key=self.api_key.strip())
        self.last_detected_language = None

    def transcribe(self, audio_file):
        if not audio_file:
            raise ValueError("Audio file path is required.")

        file_path = Path(audio_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        if file_path.stat().st_size == 0:
            raise ValueError("Audio file is empty. Please speak again.")

        try:
            with open(file_path, "rb") as f:
                res = self.client.speech_to_text.convert(
                    file=f,
                    model_id=self.model_id,
                    tag_audio_events=False
                )

            text = (getattr(res, "text", "") or "").strip()
            self.last_detected_language = getattr(res, "language_code", None)

            try:
                lang_display = self.last_detected_language or "unknown"
                safe_text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                print(f"[ELEVENLABS STT] Detected language: {lang_display}")
                print(f"[ELEVENLABS STT] Transcribed text: {safe_text}")
            except Exception:
                pass

            if not text:
                raise ValueError("No speech detected in audio. Please speak again.")

            return text

        except Exception as e:
            raise RuntimeError(f"ElevenLabs STT failed: {e}") from e