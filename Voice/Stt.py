import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

class STTService:
    def __init__(self):
        self.client=ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    def transcribe(self,audio_file):
        if not audio_file:
            raise ValueError("Audio file path is required.")
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        try:
            with open(audio_file, "rb") as file:
                result = self.client.speech_to_text.convert(file=file,model_id="scribe_v2")
            text = result.text.strip()
            if not text:
                raise ValueError("No speech detected in audio.")
            return text
        except Exception as e:
            raise RuntimeError(f"Speech-to-Text failed: {e}")