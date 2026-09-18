import sounddevice as sd
import soundfile as sf


def record_audio(filename="Voice/user_input.wav",duration=5,sample_rate=16000):
    print("🎤 Speak now...")
    audio = sd.rec(
        int(duration * sample_rate),samplerate=sample_rate,channels=1)
    sd.wait()

    sf.write(filename,audio,sample_rate)
    print("✅ Recording complete.")
    return filename