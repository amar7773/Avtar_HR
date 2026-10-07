import sys
from pathlib import Path

# Add project root to sys.path so script can be run from anywhere
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Voice.Stt import STTService


if __name__ == "__main__":
    stt = STTService()
    user_audio = PROJECT_ROOT / "Voice" / "user_input.wav"
    fallback_audio = PROJECT_ROOT / "Voice" / "ai_response.mp3"
    test_audio = user_audio if user_audio.exists() else fallback_audio
    if not test_audio.exists():
        print(f"Test audio file not found: {user_audio} or {fallback_audio}")
    else:
        print(f"Testing transcription with: {test_audio.name}")
        text = stt.transcribe(str(test_audio))
        print("Transcribed Text:")
        print(text)