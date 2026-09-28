import os
from faster_whisper import WhisperModel


class STTService:

    def __init__(self):
        self.model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8"
        )

    def transcribe(self, audio_file):

        if not audio_file:
            raise ValueError(
                "Audio file path is required."
            )

        if not os.path.exists(audio_file):
            raise FileNotFoundError(
                f"Audio file not found: {audio_file}"
            )

        try:

            segments, info = self.model.transcribe(
                audio_file,
                beam_size=5,
                language="en",
                vad_filter=False
            )

            segments = list(segments)

            text = " ".join(
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            ).strip()

            print("🎤 Detected language:", info.language)
            print("🎤 Transcribed text:", text)

            if not text:
                raise ValueError(
                    "No speech detected in audio."
                )

            return text

        except Exception as e:

            raise RuntimeError(
                f"Speech-to-Text failed: {e}"
            )