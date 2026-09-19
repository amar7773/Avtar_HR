from Voice.Tts import TTSService


tts = TTSService()


text = "Namaste, main aapki kaise madad kar sakta hoon?"


audio_file = tts.generate_speech(
    text=text
)


print("Text:")
print(text)

print("\nAudio:")
print(audio_file)