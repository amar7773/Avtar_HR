import os
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()


class TTSService:

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("voice_id")

        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "Configuration error: 'ELEVENLABS_API_KEY' is missing from the environment or .env file."
            )

        if not self.voice_id or not self.voice_id.strip():
            raise ValueError(
                "Configuration error: 'voice_id' is missing from the environment or .env file."
            )

        # Conversational low-latency multilingual model (natively supports Hindi, English, Hinglish)
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
        self.client = ElevenLabs(api_key=self.api_key.strip())
        self.cache_dir = Path(__file__).resolve().parent / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_speech(self, text, output_file="Voice/ai_response.mp3"):
        import hashlib
        import shutil

        if not text or not str(text).strip():
            raise ValueError("Text is required for TTS.")

        text = str(text).strip()
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cache_key = hashlib.md5(
            f"{self.voice_id}_{self.model_id}_{text}".encode("utf-8")
        ).hexdigest()
        cached_file = self.cache_dir / f"{cache_key}.mp3"

        if cached_file.exists() and cached_file.stat().st_size > 1000:
            try:
                if cached_file.resolve() != output_path.resolve():
                    shutil.copy2(cached_file, output_path)
                return str(output_path)
            except Exception:
                return str(cached_file)

        try:
            audio_stream = self.client.text_to_speech.convert(
                voice_id=self.voice_id.strip(),
                text=text,
                model_id=self.model_id,
                output_format="mp3_44100_128",
            )

            temp_cache = self.cache_dir / f"tmp_{cache_key}.mp3"
            with open(temp_cache, "wb") as f:
                for chunk in audio_stream:
                    if chunk:
                        f.write(chunk)

            if temp_cache.exists() and temp_cache.stat().st_size > 500:
                temp_cache.replace(cached_file)
                if cached_file.resolve() != output_path.resolve():
                    shutil.copy2(cached_file, output_path)
            elif temp_cache.exists():
                temp_cache.unlink(missing_ok=True)

        except Exception as e:
            raise RuntimeError(f"ElevenLabs TTS failed: {e}") from e

        return str(output_path if output_path.exists() else cached_file)