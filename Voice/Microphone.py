import os
import sounddevice as sd
import soundfile as sf


def record_audio(
    filename="Voice/user_input.wav",
    duration=5,
    sample_rate=16000
):

    print("🎤 Speak now...")

    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    audio_level = abs(audio).max()

    print("🔊 Audio level:", audio_level)

    if audio_level < 0.01:
        print("⚠️ Voice volume is very low.")

    os.makedirs(
        os.path.dirname(filename) or ".",
        exist_ok=True
    )

    sf.write(
        filename,
        audio,
        sample_rate,
        subtype="PCM_16"
    )

    print("✅ Recording complete.")
    print("📁 Saved:", filename)

    return filename