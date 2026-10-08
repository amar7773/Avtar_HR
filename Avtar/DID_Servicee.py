import os
import base64
import binascii
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

from Voice.Tts import TTSService


load_dotenv()

CANONICAL_RESPONSE_AUDIO = (
    Path(__file__).resolve().parents[1] / "Voice" / "ai_response.mp3"
)


class DIDService:
    def __init__(self):
        api_key = os.getenv("API_DI_ID")
        if not api_key or not api_key.strip():
            raise ValueError("API_DI_ID not found in .env")
        api_key = api_key.strip()
        if api_key.lower().startswith("basic "):
            api_key = api_key[6:].strip()
        if ":" in api_key:
            username, password = api_key.split(":", 1)
        else:
            try:
                decoded_key = base64.b64decode(api_key, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError) as error:
                raise ValueError(
                    "API_DI_ID must contain D-ID API user/password credentials."
                ) from error
            if ":" not in decoded_key:
                raise ValueError(
                    "API_DI_ID must contain D-ID API user/password credentials."
                )
            username, password = decoded_key.split(":", 1)
        if not username or not password:
            raise ValueError("API_DI_ID must contain both D-ID credential fields.")
        self.base_url = "https://api.d-id.com"
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Accept": "application/json"}

    def upload_image(self, image_path):
        """Upload a local image file to D-ID /images and return image_id + image_url."""
        filename = os.path.basename(image_path)
        mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        with open(image_path, "rb") as img_file:
            response = requests.post(
                f"{self.base_url}/images",
                headers=self.headers,
                auth=self.auth,
                files={"image": (filename, img_file, mime_type)},
                timeout=60,
            )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"D-ID image upload failed with HTTP {response.status_code}: {response.text}"
            )
        data = response.json()
        image_id, image_url = data.get("id"), data.get("url")
        if not image_id or not image_url:
            raise RuntimeError(f"D-ID image upload returned incomplete data: {data}")
        self._validate_did_url(image_url, "D-ID image URL")
        return {"image_id": image_id, "image_url": image_url}

    def upload_audio(self, audio_path):
        audio_path = Path(audio_path)
        if audio_path.resolve() != CANONICAL_RESPONSE_AUDIO.resolve():
            raise ValueError("D-ID response audio must be Voice/ai_response.mp3.")
        TTSService.validate_mp3(audio_path)
        audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        filename = audio_path.name
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                f"{self.base_url}/audios",
                headers=self.headers,
                auth=self.auth,
                files={"audio": (filename, audio_file, "audio/mpeg")},
                timeout=60,
            )
        if response.status_code != 201:
            failure_kind = {
                400: "invalid audio/request",
                401: "authentication",
                402: "credits/account",
                403: "permission",
                415: "unsupported audio format",
            }.get(response.status_code, "request")
            raise RuntimeError(
                f"D-ID audio upload {failure_kind} failure with HTTP "
                f"{response.status_code}: {response.text}"
            )
        data = response.json()
        audio_url = data.get("url")
        if not audio_url:
            raise RuntimeError(f"D-ID audio upload returned no URL: {data}")
        self._validate_did_url(audio_url, "D-ID audio URL")
        return {"url": audio_url, "audio_sha256": audio_hash}

    @staticmethod
    def _validate_did_url(url, label):
        parsed = urlparse(url or "")
        if parsed.scheme not in ("https", "s3") or not parsed.netloc:
            raise ValueError(f"{label} must be a valid HTTPS or D-ID S3 URL.")

    def create_talking_avatar(self, image_url, audio_url, expression=None):
        self._validate_did_url(image_url, "D-ID avatar image URL")
        self._validate_did_url(audio_url, "D-ID uploaded audio URL")
        payload = {
            "source_url": image_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url,
            },
            "config": {
                "stitch": True,
                "fluent": True,
                "pad_audio": 0.0,
            },
        }
        if expression:
            if expression not in {"neutral", "happy", "serious", "surprise"}:
                raise ValueError(f"Unsupported D-ID driver expression: {expression}")
            payload["config"]["driver_expressions"] = {
                "expressions": [
                    {
                        "start_frame": 0,
                        "expression": expression,
                        "intensity": 0.35,
                    }
                ],
                "transition_frames": 15,
            }
        response = requests.post(
            f"{self.base_url}/talks",
            headers={**self.headers, "Content-Type": "application/json"},
            auth=self.auth,
            json=payload,
            timeout=60,
        )
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(
                f"D-ID talk creation failed with HTTP {response.status_code}: {response.text}"
            )
        talk_id = response.json().get("id")
        if not isinstance(talk_id, str) or not re.fullmatch(r"tlk_[A-Za-z0-9_-]+", talk_id):
            raise RuntimeError(f"D-ID returned an invalid talk ID: {response.text}")
        print(f"[D-ID] Talk initiated successfully: talk_id={talk_id}")
        return talk_id

    @staticmethod
    def expression_for_response(response_text):
        normalized = re.sub(r"\s+", " ", str(response_text or "").casefold()).strip()
        if any(word in normalized for word in ("congratulations", "great news", "successfully", "excellent", "happy", "glad", "welcome", "pleasure", "hello", "hi", "hey", "namaste", "good morning", "good afternoon", "good evening", "thank", "thanks", "dhanyawad", "shukriya", "happy to help", "certainly")):
            return "happy"
        if any(word in normalized for word in ("sorry", "unfortunately", "concern", "problem", "unable", "error", "failed", "rejected", "absent", "cannot")):
            return "serious"
        if any(word in normalized for word in ("surprisingly", "unexpected", "wow", "amazing")):
            return "surprise"
        return "neutral"

    def get_talk_status(self, talk_id):
        if not isinstance(talk_id, str) or not re.fullmatch(r"tlk_[A-Za-z0-9_-]+", talk_id):
            raise ValueError("A real D-ID talk ID is required for status polling.")
        response = requests.get(
            f"{self.base_url}/talks/{talk_id}",
            headers=self.headers,
            auth=self.auth,
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"D-ID status request for talk {talk_id} failed with HTTP "
                f"{response.status_code}: {response.text}"
            )
        data = response.json()
        if data.get("id") != talk_id:
            raise RuntimeError(
                f"D-ID returned status for {data.get('id')}, expected {talk_id}."
            )
        status = data.get("status")
        result_url = data.get("result_url")
        return {
            "talk_id": talk_id,
            "status": status,
            "result_url": result_url,
            "data": data,
        }

    @staticmethod
    def validate_video(video_path):
        video_path = Path(video_path)
        if not video_path.is_file() or video_path.stat().st_size == 0:
            raise ValueError(f"D-ID MP4 is missing or empty: {video_path}")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise RuntimeError("ffprobe is required to validate D-ID MP4 output.")
        probe = subprocess.run(
            [
                ffprobe, "-v", "error", "-show_entries", "stream=codec_type",
                "-show_entries", "format=format_name,duration", "-of", "json",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if probe.returncode:
            raise ValueError(f"Invalid D-ID MP4: {probe.stderr.strip()}")
        metadata = json.loads(probe.stdout)
        stream_types = {stream.get("codec_type") for stream in metadata.get("streams", [])}
        duration = float(metadata.get("format", {}).get("duration", 0))
        if (
            "video" not in stream_types
            or "audio" not in stream_types
            or "mp4" not in metadata.get("format", {}).get("format_name", "")
            or duration <= 0
        ):
            raise ValueError("D-ID result must be an MP4 with audio, video, and duration.")
        return video_path

    @staticmethod
    def download_video(result_url, output_path):
        DIDService._validate_did_url(result_url, "D-ID result URL")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.stem}.", suffix=".tmp", dir=output_path.parent
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            with requests.get(result_url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with temporary_path.open("wb") as video_file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            video_file.write(chunk)
            DIDService.validate_video(temporary_path)
            os.replace(temporary_path, output_path)
            return output_path
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def start_talking_avatar_from_audio(self, image_url, audio_path, expression=None):
        self._validate_did_url(image_url, "D-ID avatar image URL")
        upload = self.upload_audio(audio_path)
        audio_url = upload["url"]
        talk_id = self.create_talking_avatar(
            image_url=image_url,
            audio_url=audio_url,
            expression=expression,
        )
        return {
            "talk_id": talk_id,
            "audio_url": audio_url,
            "audio_sha256": upload["audio_sha256"],
            "status": "processing",
        }

    def wait_for_video(self, talk_id, timeout=120, interval=3):
        start_time = time.time()
        while time.time() - start_time < timeout:
            data_info = self.get_talk_status(talk_id)
            status = data_info.get("status")

            if status == "done":
                result_url = data_info.get("result_url")
                if result_url:
                    return result_url
                raise RuntimeError(
                    f"D-ID completed but no result_url was returned. "
                    f"Response: {data_info.get('data')}"
                )
            if status in ("error", "failed", "rejected"):
                raise RuntimeError(
                    f"D-ID avatar generation failed: {data_info.get('data')}"
                )
            time.sleep(interval)
        raise TimeoutError(
            f"D-ID avatar generation timed out for talk_id={talk_id}"
        )

    def create_stream(self, source_url):
        self._validate_did_url(source_url, "D-ID avatar image URL")
        response = requests.post(
            f"{self.base_url}/talks/streams",
            headers={**self.headers, "Content-Type": "application/json"},
            auth=self.auth,
            json={"source_url": source_url, "stream_warmup": True},
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"D-ID stream creation failed ({response.status_code}): {response.text}"
            )
        return response.json()

    def send_stream_sdp(self, stream_id, answer, session_id):
        response = requests.post(
            f"{self.base_url}/talks/streams/{stream_id}/sdp",
            headers={**self.headers, "Content-Type": "application/json"},
            auth=self.auth,
            json={"answer": answer, "session_id": session_id},
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"D-ID stream SDP failed ({response.status_code}): {response.text}"
            )
        return response.json()

    def send_stream_ice(self, stream_id, candidate, sdp_mid, sdp_mline_index, session_id):
        response = requests.post(
            f"{self.base_url}/talks/streams/{stream_id}/ice",
            headers={**self.headers, "Content-Type": "application/json"},
            auth=self.auth,
            json={
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index,
                "session_id": session_id,
            },
            timeout=30,
        )
        return response.status_code in (200, 201)

    def talk_stream(self, stream_id, session_id, script, expression=None):
        payload = {
            "script": script,
            "session_id": session_id,
            "config": {"stitch": True},
        }
        if expression and expression in {"neutral", "happy", "serious", "surprise"}:
            payload["config"]["driver_expressions"] = {
                "expressions": [
                    {
                        "start_frame": 0,
                        "expression": expression,
                        "intensity": 0.35,
                    }
                ],
                "transition_frames": 15,
            }
        response = requests.post(
            f"{self.base_url}/talks/streams/{stream_id}",
            headers={**self.headers, "Content-Type": "application/json"},
            auth=self.auth,
            json=payload,
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"D-ID stream talk failed ({response.status_code}): {response.text}"
            )
        return response.json()

    def talk_stream_from_audio(self, stream_id, session_id, audio_path, expression=None):
        """Upload canonical ElevenLabs MP3 to D-ID and immediately stream speech over WebRTC."""
        upload_info = self.upload_audio(audio_path)
        audio_url = upload_info.get("url")
        if not audio_url:
            raise RuntimeError("Audio upload returned no URL for D-ID stream talk.")
        script = {"type": "audio", "audio_url": audio_url}
        return self.talk_stream(stream_id, session_id, script, expression=expression)

    def close_stream(self, stream_id, session_id=""):
        try:
            requests.delete(
                f"{self.base_url}/talks/streams/{stream_id}",
                headers={**self.headers, "Content-Type": "application/json"},
                auth=self.auth,
                json={"session_id": session_id} if session_id else {},
                timeout=15,
            )
        except Exception:
            pass

