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

    def generate_speech(
        self,
        text,
        output_file="Voice/ai_response.mp3"
    ):
        if not text or not str(text).strip():
            raise ValueError("Text is required for TTS.")

        text = str(text).strip()
        print(f"TTS voice: {self.voice_id}")
        print(f"TTS output: {output_file}")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            audio_stream = self.client.text_to_speech.convert(
                voice_id=self.voice_id.strip(),
                text=text,
                model_id=self.model_id,
                output_format="mp3_44100_128",
            )

            with open(output_path, "wb") as f:
                for chunk in audio_stream:
                    if chunk:
                        f.write(chunk)

        except Exception as e:
            raise RuntimeError(f"ElevenLabs TTS failed: {e}") from e

        return str(output_path)