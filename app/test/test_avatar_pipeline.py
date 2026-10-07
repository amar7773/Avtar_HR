import hashlib
import shutil
import subprocess
import threading
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from Avtar.DID_Servicee import DIDService
from Api import main as avatar_api
from Voice.Tts import TTSService
from Voice.response_audio_lock import lock_response_audio


def _make_audio(path, frequency):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is required to create a playable MP3 test fixture.")
    subprocess.run(
        [
            ffmpeg, "-v", "error", "-f", "lavfi", "-i",
            f"sine=frequency={frequency}:duration=0.4", "-codec:a", "libmp3lame",
            "-q:a", "5", "-y", str(path),
        ],
        check=True,
        timeout=30,
    )
    return path.read_bytes()


def _make_video(path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is required to create a valid MP4 test fixture.")
    subprocess.run(
        [
            ffmpeg, "-v", "error", "-f", "lavfi", "-i",
            "color=c=black:s=160x120:r=25", "-f", "lavfi", "-i",
            "sine=frequency=440:duration=0.5", "-t", "0.5", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-y", str(path),
        ],
        check=True,
        timeout=30,
    )
    return path.read_bytes()


class _FakeTTS:
    def __init__(self, audio_responses):
        self.responses = iter(audio_responses)

    def convert(self, **_kwargs):
        return BytesIO(next(self.responses))


def _tts_service(audio_responses):
    service = object.__new__(TTSService)
    service.voice_id = "test-voice"
    service.model_id = "test-model"
    service.client = SimpleNamespace(text_to_speech=_FakeTTS(audio_responses))
    service._generation_lock = __import__("threading").Lock()
    service._generated_outputs = {}
    return service


def _did_service():
    service = object.__new__(DIDService)
    service.base_url = "https://api.d-id.com"
    service.headers = {"Accept": "application/json"}
    service.auth = None
    return service


def test_avatar_greeting_uses_prerendered_video_when_available(monkeypatch, tmp_path):
    avatar_dir = tmp_path / "Avtar"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    greeting_file = avatar_dir / "greeting_avatar.mp4"
    greeting_file.write_bytes(b"dummy video data exceeding 10000 bytes " * 300)
    monkeypatch.setattr(avatar_api, "AVATAR_DIR", avatar_dir)

    result = avatar_api.get_avatar_greeting()
    assert result["status"] == "ready"
    assert "greeting_avatar.mp4" in result["video_url"]
    assert result["talk_id"] is None


def test_avatar_greeting_generates_audio_and_returns_real_talk_id(monkeypatch, tmp_path):
    avatar_dir = tmp_path / "Avtar"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(avatar_api, "AVATAR_DIR", avatar_dir)

    generated = {}
    assistant = SimpleNamespace(
        _audio_pipeline_lock=threading.Lock(),
        tts_service=SimpleNamespace(
            generate_speech=lambda **kwargs: generated.setdefault(
                "audio_path", kwargs["output_file"]
            )
        ),
        start_avatar=lambda audio_path, text: {
            "talk_id": "tlk_greeting_123",
            "status": "processing",
        },
    )
    monkeypatch.setattr(avatar_api, "get_assistant", lambda: assistant)
    monkeypatch.setattr(avatar_api, "lock_response_audio", lambda _path: nullcontext())

    result = avatar_api.get_avatar_greeting()

    assert generated["audio_path"] == str(avatar_api.VOICE_DIR / "ai_response.mp3")
    assert result["talk_id"] == "tlk_greeting_123"
    assert result["status"] == "processing"


def test_tts_overwrites_one_canonical_file_with_valid_current_mp3(tmp_path):
    first_mp3 = _make_audio(tmp_path / "first.mp3", 440)
    second_mp3 = _make_audio(tmp_path / "second.mp3", 880)
    output_path = tmp_path / "Voice" / "ai_response.mp3"
    service = _tts_service([first_mp3, second_mp3])

    assert Path(service.generate_speech("First response", str(output_path))) == output_path
    first_hash = service.validate_generated_speech("First response", output_path)
    assert first_hash == hashlib.sha256(first_mp3).hexdigest()

    assert Path(service.generate_speech("Second response", str(output_path))) == output_path
    second_hash = service.validate_generated_speech("Second response", output_path)
    assert second_hash == hashlib.sha256(second_mp3).hexdigest()
    assert output_path.read_bytes() == second_mp3
    assert list(output_path.parent.glob("resp_*.mp3")) == []
    assert list(output_path.parent.glob("*.mp3")) == [output_path]


def test_response_audio_lock_serializes_concurrent_threads(tmp_path):
    audio_path = tmp_path / "ai_response.mp3"
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first_request():
        with lock_response_audio(audio_path):
            first_entered.set()
            release_first.wait(timeout=5)

    def second_request():
        first_entered.wait(timeout=5)
        with lock_response_audio(audio_path):
            second_entered.set()

    first = threading.Thread(target=first_request)
    second = threading.Thread(target=second_request)
    first.start()
    second.start()
    assert first_entered.wait(timeout=5)
    assert not second_entered.wait(timeout=0.1)
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert second_entered.is_set()
    assert not first.is_alive()
    assert not second.is_alive()


def test_audio_upload_uses_canonical_mp3_and_returns_did_url(tmp_path, monkeypatch):
    audio_bytes = _make_audio(tmp_path / "fixture.mp3", 600)
    canonical_path = tmp_path / "ai_response.mp3"
    canonical_path.write_bytes(audio_bytes)
    monkeypatch.setattr("Avtar.DID_Servicee.CANONICAL_RESPONSE_AUDIO", canonical_path)
    service = _did_service()
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["audio"] = kwargs["files"]["audio"]
        captured["audio_bytes"] = captured["audio"][1].read()
        captured["auth"] = kwargs["auth"]
        return SimpleNamespace(
            status_code=201,
            json=lambda: {"url": "s3://d-id-audios-prod/account/current-response.mp3"},
        )

    monkeypatch.setattr("Avtar.DID_Servicee.requests.post", fake_post)
    result = service.upload_audio(canonical_path)

    assert result["url"] == "s3://d-id-audios-prod/account/current-response.mp3"
    assert result["audio_sha256"] == hashlib.sha256(audio_bytes).hexdigest()
    assert captured["url"] == "https://api.d-id.com/audios"
    assert captured["audio"][0] == "ai_response.mp3"
    assert captured["audio"][2] == "audio/mpeg"
    assert captured["audio_bytes"] == audio_bytes


def test_talk_payload_and_polling_use_real_returned_talk_id(monkeypatch):
    service = _did_service()
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return SimpleNamespace(
            status_code=201,
            text='{"id":"tlk_current_123"}',
            json=lambda: {"id": "tlk_current_123"},
        )

    monkeypatch.setattr("Avtar.DID_Servicee.requests.post", fake_post)
    talk_id = service.create_talking_avatar(
        "s3://d-id-images-prod/account/avatar.jpg",
        "s3://d-id-audios-prod/account/response.mp3",
    )

    assert talk_id == "tlk_current_123"
    assert calls == [
        (
            "https://api.d-id.com/talks",
            {
                "source_url": "s3://d-id-images-prod/account/avatar.jpg",
                "script": {
                    "type": "audio",
                    "audio_url": "s3://d-id-audios-prod/account/response.mp3",
                },
                "config": {
                    "stitch": True,
                    "fluent": True,
                    "pad_audio": 0.0,
                },
            },
        )
    ]

    status_calls = []

    def fake_get(url, **_kwargs):
        status_calls.append(url)
        return SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {
                "id": "tlk_current_123",
                "status": "done",
                "result_url": "https://cdn.example.test/tlk_current_123.mp4",
            },
        )

    monkeypatch.setattr("Avtar.DID_Servicee.requests.get", fake_get)
    assert service.wait_for_video(talk_id, timeout=0.1, interval=0) == (
        "https://cdn.example.test/tlk_current_123.mp4"
    )
    assert status_calls == ["https://api.d-id.com/talks/tlk_current_123"]


def test_response_reaction_uses_documented_driver_expression_config(monkeypatch):
    service = _did_service()
    captured = {}

    def fake_post(_url, **kwargs):
        captured["payload"] = kwargs["json"]
        return SimpleNamespace(
            status_code=201,
            text='{"id":"tlk_expression_123"}',
            json=lambda: {"id": "tlk_expression_123"},
        )

    monkeypatch.setattr("Avtar.DID_Servicee.requests.post", fake_post)
    expression = service.expression_for_response(
        "Congratulations, your request was completed successfully."
    )
    assert expression == "happy"
    service.create_talking_avatar(
        "s3://d-id-images-prod/account/avatar.jpg",
        "s3://d-id-audios-prod/account/response.mp3",
        expression=expression,
    )
    assert captured["payload"]["config"] == {
        "stitch": True,
        "fluent": True,
        "pad_audio": 0.0,
        "driver_expressions": {
            "expressions": [
                {"start_frame": 0, "expression": "happy", "intensity": 0.35}
            ],
            "transition_frames": 15,
        },
    }


def test_talk_rejects_missing_talk_id_and_reports_http_failure(monkeypatch):
    service = _did_service()
    monkeypatch.setattr(
        "Avtar.DID_Servicee.requests.post",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=500, text='{"kind":"UnknownError"}'
        ),
    )
    with pytest.raises(RuntimeError, match="HTTP 500"):
        service.create_talking_avatar(
            "https://example.test/avatar.jpg",
            "https://example.test/audio.mp3",
        )


def test_audio_upload_reports_did_permission_failure(tmp_path, monkeypatch):
    audio_bytes = _make_audio(tmp_path / "fixture.mp3", 520)
    canonical_path = tmp_path / "ai_response.mp3"
    canonical_path.write_bytes(audio_bytes)
    monkeypatch.setattr("Avtar.DID_Servicee.CANONICAL_RESPONSE_AUDIO", canonical_path)
    service = _did_service()
    monkeypatch.setattr(
        "Avtar.DID_Servicee.requests.post",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=403, text='{"message":"Forbidden"}'
        ),
    )

    with pytest.raises(RuntimeError, match=r"HTTP 403.*Forbidden"):
        service.upload_audio(canonical_path)


def test_download_requires_mp4_with_audio_and_video(tmp_path, monkeypatch):
    video_bytes = _make_video(tmp_path / "fixture.mp4")
    output_path = tmp_path / "downloaded.mp4"

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            assert chunk_size == 1024 * 1024
            yield video_bytes

    monkeypatch.setattr(
        "Avtar.DID_Servicee.requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    assert DIDService.download_video(
        "https://cdn.example.test/talk.mp4", output_path
    ) == output_path
    assert output_path.read_bytes() == video_bytes
