import sys
from pathlib import Path

# Add project root to sys.path so script can be run from anywhere
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Voice.Microphone import record_audio
from Voice.Stt import STTService


if __name__ == "__main__":
    stt = STTService()
    audio_file = record_audio(duration=5)
    text = stt.transcribe(audio_file)

    print("\n==============================")
    print("🎤 You said:")
    print(text)
    print("==============================")