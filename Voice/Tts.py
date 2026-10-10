import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()


_validated_mp3_hashes = set()


class TTSService:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("voice_id")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("ELEVENLABS_API_KEY is missing from the environment.")
        if not self.voice_id or not self.voice_id.strip():
            raise ValueError("voice_id is missing from the environment.")

        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
        self.client = ElevenLabs(api_key=self.api_key.strip())
        self._generation_lock = threading.Lock()
        self._generated_outputs = {}

    @staticmethod
    def clean_for_speech(text: str) -> str:
        """Strip markdown syntax, bullet markers, and code formatting for natural human-like spoken flow."""
        if not text:
            return ""
        s = str(text).strip()
        # Remove markdown links [text](url) -> text
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        # Remove bold / italics: **word** or *word* or __word__
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"__([^_]+)__", r"\1", s)
        s = re.sub(r"_([^_]+)_", r"\1", s)
        # Remove markdown headers #, ##, etc.
        s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
        # Remove backticks / code blocks
        s = re.sub(r"```[a-zA-Z]*\n?([\s\S]*?)```", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        # Convert bullet points (- item, * item) to clean pauses
        s = re.sub(r"^\s*[-*•]\s+", "", s, flags=re.MULTILINE)
        # Remove emojis that TTS might read aloud awkwardly
        s = re.sub(r"[\U00010000-\U0010ffff]", "", s)
        # Normalize linebreaks to natural sentence pauses
        s = re.sub(r"\n+", ". ", s)
        s = re.sub(r"\s+", " ", s).strip()
        # Clean double punctuation
        s = re.sub(r"\.+", ".", s)
        s = re.sub(r"\s*,\s*", ", ", s)
        return s or str(text).strip()

    @staticmethod
    def validate_mp3(audio_path):
        path = Path(audio_path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Generated MP3 is missing or empty: {path}")

        audio_bytes = path.read_bytes()
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()
        if audio_hash in _validated_mp3_hashes:
            return audio_hash

        # Fast header validation to eliminate 200-350ms ffprobe subprocess when audio is clean MP3
        if len(audio_bytes) >= 512:
            is_id3 = len(audio_bytes) > 10 and audio_bytes[:3] == b"ID3"
            is_sync = len(audio_bytes) > 4 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0
            if is_id3 or is_sync:
                _validated_mp3_hashes.add(audio_hash)
                return audio_hash

        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise RuntimeError("ffprobe is required to validate generated MP3 audio.")
        result = subprocess.run(
            [
                ffprobe, "-v", "error", "-show_entries",
                "stream=codec_type,codec_name", "-show_entries",
                "format=duration", "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode:
            raise ValueError(f"Generated MP3 is not playable: {result.stderr.strip()}")
        metadata = json.loads(result.stdout)
        has_mp3_audio = any(
            stream.get("codec_type") == "audio" and stream.get("codec_name") == "mp3"
            for stream in metadata.get("streams", [])
        )
        duration = float(metadata.get("format", {}).get("duration", 0))
        if not has_mp3_audio or duration <= 0:
            raise ValueError("Generated file contains no playable MP3 audio.")
        _validated_mp3_hashes.add(audio_hash)
        return audio_hash

    def validate_generated_speech(self, text, output_file):
        path = Path(output_file).resolve()
        generated = self._generated_outputs.get(path)
        text_hash = hashlib.sha256(str(text).strip().encode("utf-8")).hexdigest()
        if not generated or generated[0] != text_hash:
            raise ValueError("The response MP3 was not generated for the current AI response.")
        self.validate_mp3(path)
        audio_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if generated[1] != audio_hash:
            raise ValueError("The response MP3 changed after generation.")
        return audio_hash

    def generate_speech(self, text, output_file=None):
        if not text or not str(text).strip():
            raise ValueError("Text is required for TTS.")
        text = str(text).strip()
        spoken_text = self.clean_for_speech(text)
        output_path = (
            Path(output_file)
            if output_file
            else Path(__file__).resolve().parent / "ai_response.mp3"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._generation_lock:
            descriptor, temp_name = tempfile.mkstemp(
                prefix=".ai_response.", suffix=".tmp", dir=str(output_path.parent)
            )
            os.close(descriptor)
            temporary_path = Path(temp_name)
            try:
                # Fast path: Request 24kHz mono PCM directly from ElevenLabs
                convert_kwargs = {
                    "voice_id": self.voice_id.strip(),
                    "text": spoken_text,
                    "model_id": self.model_id,
                    "output_format": "pcm_24000",
                }
                try:
                    from elevenlabs import VoiceSettings
                    convert_kwargs["voice_settings"] = VoiceSettings(
                        stability=0.50,
                        similarity_boost=0.75,
                        use_speaker_boost=True,
                        speed=0.92,
                    )
                except Exception:
                    pass

                try:
                    audio_stream = self.client.text_to_speech.convert(**convert_kwargs)
                    raw_chunks = []
                    for chunk in audio_stream:
                        if chunk:
                            raw_chunks.append(chunk)
                    raw_audio_bytes = b"".join(raw_chunks)
                except Exception as stream_err:
                    # Fallback to standard MP3 if provider does not support direct PCM
                    convert_kwargs["output_format"] = "mp3_44100_128"
                    audio_stream = self.client.text_to_speech.convert(**convert_kwargs)
                    raw_chunks = []
                    for chunk in audio_stream:
                        if chunk:
                            raw_chunks.append(chunk)
                    raw_audio_bytes = b"".join(raw_chunks)

                pcm_path = output_path.with_name(f"{output_path.stem}_24k.pcm")
                ffmpeg = shutil.which("ffmpeg")

                # Detect if returned bytes are MP3 (e.g. from tests or fallback) or raw PCM
                is_mp3 = (
                    len(raw_audio_bytes) > 4
                    and (
                        raw_audio_bytes[:3] == b"ID3"
                        or (raw_audio_bytes[0] == 0xFF and (raw_audio_bytes[1] & 0xE0) == 0xE0)
                    )
                )

                if is_mp3:
                    # MP3 payload
                    with temporary_path.open("wb") as audio_file:
                        audio_file.write(raw_audio_bytes)
                    self.validate_mp3(temporary_path)
                    audio_hash = hashlib.sha256(raw_audio_bytes).hexdigest()
                    os.replace(temporary_path, output_path)
                    self._generated_outputs[output_path.resolve()] = (
                        hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        audio_hash,
                    )
                    # Convert MP3 to 24kHz PCM for avatar
                    if ffmpeg and output_path.is_file():
                        p = subprocess.run(
                            [
                                ffmpeg, "-y", "-i", str(output_path),
                                "-f", "s16le", "-acodec", "pcm_s16le",
                                "-ac", "1", "-ar", "24000",
                                str(pcm_path),
                            ],
                            capture_output=True, check=False, timeout=10,
                        )
                        if pcm_path.is_file():
                            pcm_bytes = pcm_path.read_bytes()
                            import base64
                            self.last_pcm_base64 = base64.b64encode(pcm_bytes).decode("ascii")
                else:
                    # Raw 24kHz 16-bit PCM payload directly from ElevenLabs
                    pcm_bytes = raw_audio_bytes
                    pcm_path.write_bytes(pcm_bytes)
                    import base64
                    self.last_pcm_base64 = base64.b64encode(pcm_bytes).decode("ascii")

                    # Fast-encode PCM to MP3 using ffmpeg (-threads 4 for ~40ms speed on Windows)
                    if ffmpeg:
                        subprocess.run(
                            [
                                ffmpeg, "-y", "-threads", "4",
                                "-f", "s16le", "-ar", "24000", "-ac", "1",
                                "-i", str(pcm_path),
                                "-c:a", "libmp3lame", "-b:a", "128k",
                                str(temporary_path),
                            ],
                            capture_output=True, check=False, timeout=10,
                        )

                    if temporary_path.is_file() and temporary_path.stat().st_size > 0:
                        self.validate_mp3(temporary_path)
                        audio_hash = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
                        os.replace(temporary_path, output_path)
                        self._generated_outputs[output_path.resolve()] = (
                            hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            audio_hash,
                        )
                    else:
                        temporary_path.write_bytes(pcm_bytes)
                        os.replace(temporary_path, output_path)

                return str(output_path)
            except Exception as error:
                temporary_path.unlink(missing_ok=True)
                if isinstance(error, (RuntimeError, ValueError)):
                    raise
                raise RuntimeError(f"ElevenLabs TTS failed: {error}") from error

    def ensure_canonical_greeting(self, greeting_text="Hi, I am your AI employee assistant. How can I help you today?"):
        """Ensure greeting.mp3 and greeting_24k.pcm exist with canonical slower voice settings."""
        greeting_mp3 = Path(__file__).resolve().parent / "greeting.mp3"
        greeting_pcm = Path(__file__).resolve().parent / "greeting_24k.pcm"
        if not greeting_mp3.is_file() or not greeting_pcm.is_file():
            self.generate_speech(text=greeting_text, output_file=str(greeting_mp3))
        return str(greeting_mp3)
