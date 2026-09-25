import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()
class TTSService:
    def __init__(self):
        self.client=ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.voice_id=os.getenv("voice_id")
    def generate_speech(self,text,output_file="Voice/ai_response.mp3"):
        if not text or not str(text).strip():
            raise ValueError("Text is required for TTS.")
        text = str(text).strip()
        if not self.voice_id:
            raise ValueError("ELEVENLABS_VOICE_ID is missing in .env")
        audio=self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            voice_settings={
                "stability": 0.65,
                "similarity_boost": 0.80,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": 0.85
            }
            )
        with open(output_file,"wb") as file:
            for chunk in audio:
                if chunk:
                    file.write(chunk)
        return output_file