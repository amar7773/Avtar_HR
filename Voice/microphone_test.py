from Voice.Microphone import record_audio
from Voice.Stt import STTService

stt=STTService()
audio_file = record_audio(
    duration=5
)
text = stt.transcribe(
    audio_file
)


print("\n==============================")
print("🎤 You said:")
print(text)
print("==============================")