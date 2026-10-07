import sys
from pathlib import Path

# Add project root to sys.path so script can be run from anywhere
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Voice.Tts import TTSService


if __name__ == "__main__":
    tts = TTSService()
    text = "Namaste, main aapki kaise madad kar sakta hoon?"
    audio_file = tts.generate_speech(text=text)

    print("Text:")
    print(text)
    print("\nAudio:")
    print(audio_file)