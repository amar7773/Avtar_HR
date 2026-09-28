from Voice.Stt import STTService


stt = STTService()

text = stt.transcribe("Voice/ai_response.mp3")

print("Transcribed Text:")
print(text)