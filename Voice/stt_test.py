from Voice.Stt import STTService


stt = STTService()

text = stt.transcribe("Voice/test.wav")

print("Transcribed Text:")
print(text)