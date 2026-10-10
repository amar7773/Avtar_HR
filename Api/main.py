import os
import sys
from pathlib import Path
from uuid import uuid4
import re

# Ensure Windows terminal doesn't crash on Devanagari or Unicode prints
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from threading import Lock
from Voice.response_audio_lock import lock_response_audio

active_talk_id_lock = Lock()
latest_active_talk_id = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = PROJECT_ROOT / "Voice"
AVATAR_DIR = PROJECT_ROOT / "Avtar"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AI Employee Assistant",
    description="AI Employee Assistant API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/voice-files",
    StaticFiles(directory=str(VOICE_DIR)),
    name="voice-files"
)
app.mount(
    "/avatar-files",
    StaticFiles(directory=str(AVATAR_DIR)),
    name="avatar-files"
)


@app.on_event("startup")
def startup_warmup():
    import threading

    def _warm():
        try:
            asst = get_assistant()
            if hasattr(asst, "rag_service"):
                asst.rag_service._get_model()
        except Exception as e:
            print(f"[WARMUP INFO] Background warmup: {e}")

    threading.Thread(target=_warm, daemon=True).start()


assistant = None
assistant_lock = Lock()
auth_service = None
auth_service_lock = Lock()


def get_auth_service():
    global auth_service

    if auth_service is None:
        with auth_service_lock:
            if auth_service is None:
                from app.Services.Auth import AuthService

                auth_service = AuthService()

    return auth_service


def get_assistant():
    global assistant

    if assistant is None:
        with assistant_lock:
            if assistant is None:
                from app.Services.Assistant import AssistantService

                assistant = AssistantService()

    return assistant


class LoginRequest(BaseModel):
    employee_id: str


class ChatRequest(BaseModel):
    user_query: str
    employee_id: str
    mode: str = "text_mode"
    stream_id: Optional[str] = None
    session_id: Optional[str] = None
    avatar_provider: Optional[str] = None
    history_channel: Optional[str] = None


class TTSRequest(BaseModel):
    text: str


class StreamSdpRequest(BaseModel):
    stream_id: str
    session_id: str
    answer: dict


class StreamIceRequest(BaseModel):
    stream_id: str
    session_id: str
    candidate: str
    sdp_mid: Optional[str] = None
    sdp_mline_index: Optional[int] = None


class StreamTalkRequest(BaseModel):
    stream_id: str
    session_id: str
    text: Optional[str] = None
    audio_url: Optional[str] = None


class LiveAvatarSessionRequest(BaseModel):
    avatar_id: Optional[str] = None
    mode: str = "LITE"
    is_sandbox: bool = False
    quality: str = "medium"
    language: str = "en"
    voice_id: Optional[str] = None
    context_id: Optional[str] = None


class LiveAvatarStartRequest(BaseModel):
    session_token: str


class LiveAvatarStopRequest(BaseModel):
    session_token: str


def save_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    allowed_suffixes = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}

    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format."
        )

    return VOICE_DIR / f"{uuid4().hex}{suffix}"


def safe_unlink(path: Path, retries: int = 3, delay: float = 0.05):
    """Safely unlink a temporary file on Windows where decoders may briefly hold the file handle."""
    import time
    import gc

    if not path:
        return

    for _ in range(retries):
        try:
            if path.exists():
                path.unlink(missing_ok=True)
            return
        except PermissionError:
            gc.collect()
            time.sleep(delay)
        except Exception as e:
            print(f"[CLEANUP WARNING] Could not remove temporary file {path.name}: {e}")
            return

    try:
        if path.exists():
            path.unlink(missing_ok=True)
    except Exception:
        # Best effort cleanup, never break the ASGI request
        pass


@app.get("/")
def home():
    return {
        "message": "AI Employee Assistant API is running",
        "status": "success"
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = PROJECT_ROOT / "frontend" / "public" / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    return Response(status_code=204)


@app.post("/login")
def login(request: LoginRequest):

    result = get_auth_service().login(request.employee_id)

    if not result["success"]:
        return result

    return result


@app.post("/chat")
def chat(request: ChatRequest):
    if request.mode == "avatar_mode":
        result = get_assistant().process_text(
            user_query=request.user_query,
            employee_id=request.employee_id,
            mode="avatar_mode",
            stream_id=request.stream_id,
            session_id=request.session_id,
            avatar_provider=request.avatar_provider,
            history_channel=request.history_channel,
        )
        avatar = result.get("avatar") or {}
        if avatar.get("talk_id"):
            global latest_active_talk_id
            with active_talk_id_lock:
                latest_active_talk_id = avatar["talk_id"]

        pcm_base64 = None
        pcm_file = VOICE_DIR / "ai_response_24k.pcm"
        if pcm_file.is_file():
            try:
                import base64
                pcm_base64 = base64.b64encode(pcm_file.read_bytes()).decode("ascii")
            except Exception as e:
                print(f"[PCM ENCODE WARNING] {e}")

        return {
            "mode": "avatar_mode",
            "language": result.get("language", "English"),
            "user_text": request.user_query,
            "response": result.get("response", ""),
            "audio_url": f"/voice-files/ai_response.mp3?v={uuid4().hex}",
            "pcm_url": f"/voice-files/ai_response_24k.pcm?v={uuid4().hex}",
            "pcm_base64": pcm_base64,
            "avatar": avatar,
            "avatar_status": avatar.get("status", "idle"),
            "avatar_talk_id": avatar.get("talk_id"),
            "avatar_video_url": avatar.get("video_url"),
            "avatar_error": avatar.get("error"),
            "stream_talk": bool(avatar.get("is_stream")),
        }

    result = get_assistant().process(
        user_query=request.user_query,
        employee_id=request.employee_id,
        history_channel=request.history_channel or str(request.employee_id),
    )
    result["mode"] = "text_mode"
    return result


@app.post("/tts")
def text_to_speech(request: TTSRequest):

    text = request.text.strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text is required."
        )

    assistant_service = get_assistant()
    with assistant_service._audio_pipeline_lock, lock_response_audio(
        VOICE_DIR / "ai_response.mp3"
    ):
        audio_file = assistant_service.tts_service.generate_speech(
            text=text,
            output_file=str(VOICE_DIR / "ai_response.mp3"),
        )

    return FileResponse(
        path=audio_file,
        media_type="audio/mpeg",
        filename="ai_response.mp3",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):

    input_audio_path = save_upload(audio)

    try:
        with input_audio_path.open("wb") as file:
            file.write(await audio.read())

        try:
            text = get_assistant().stt_service.transcribe(
                str(input_audio_path)
            )
            return {
                "text": text,
                "no_speech": False,
            }
        except ValueError as ve:
            if "no speech" in str(ve).lower() or "empty" in str(ve).lower():
                return {"text": "", "no_speech": True}
            raise HTTPException(status_code=400, detail=str(ve)) from ve
        except Exception as exc:
            err_msg = str(exc).lower()
            if "no speech" in err_msg or "empty" in err_msg:
                return {"text": "", "no_speech": True}
            raise HTTPException(status_code=502, detail=f"Speech transcription failed: {exc}") from exc
    finally:
        safe_unlink(input_audio_path)


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    employee_id: str = Form(...),
    mode: str = Form(default="avatar_mode"),
    stream_id: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    avatar_provider: Optional[str] = Form(default=None),
    history_channel: Optional[str] = Form(default=None),
):

    input_audio_path = save_upload(audio)

    try:
        with input_audio_path.open("wb") as file:
            file.write(await audio.read())

        result = get_assistant().process_speech_to_speech(
            audio_file=str(input_audio_path),
            employee_id=employee_id,
            mode=mode,
            stream_id=stream_id,
            session_id=session_id,
            avatar_provider=avatar_provider,
            history_channel=history_channel,
        )
    except Exception as error:
        err_msg = str(error).lower()
        if any(k in err_msg for k in ("no speech", "empty", "silence")):
            result = {
                "no_speech": True,
                "user_query": "",
                "response": "",
                "mode": mode,
                "avatar": {"status": "idle"},
            }
        else:
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error
    finally:
        safe_unlink(input_audio_path)

    if result.get("no_speech"):
        return {
            "no_speech": True,
            "mode": result.get("mode", mode),
            "language": "English",
            "user_text": "",
            "response": "",
            "audio_url": None,
            "pcm_url": None,
            "avatar": {"status": "idle"},
            "avatar_status": "idle",
            "avatar_talk_id": None,
            "avatar_video_url": None,
            "avatar_error": None,
            "stream_talk": False,
        }

    response_audio = result.get("response_audio")
    expected_audio = VOICE_DIR / "ai_response.mp3"
    if not response_audio or Path(response_audio).resolve() != expected_audio.resolve():
        raise HTTPException(
            status_code=502,
            detail="The voice assistant did not generate Voice/ai_response.mp3."
        )
    avatar = result.get("avatar") or {}
    if avatar.get("talk_id"):
        global latest_active_talk_id
        with active_talk_id_lock:
            latest_active_talk_id = avatar["talk_id"]

    pcm_base64 = result.get("pcm_base64")
    if not pcm_base64:
        pcm_file = VOICE_DIR / "ai_response_24k.pcm"
        if pcm_file.is_file():
            try:
                import base64
                pcm_base64 = base64.b64encode(pcm_file.read_bytes()).decode("ascii")
            except Exception as e:
                print(f"[PCM ENCODE WARNING] {e}")

    return {
        "mode": result.get("mode", mode),
        "language": result.get("language", "English"),
        "user_text": result.get("user_query", ""),
        "response": result.get("response", ""),
        "audio_url": f"/voice-files/ai_response.mp3?v={uuid4().hex}",
        "pcm_url": f"/voice-files/ai_response_24k.pcm?v={uuid4().hex}",
        "pcm_base64": pcm_base64,
        "avatar": avatar,
        "avatar_status": avatar.get("status", "idle"),
        "avatar_talk_id": avatar.get("talk_id"),
        "avatar_video_url": avatar.get("video_url"),
        "avatar_error": avatar.get("error"),
        "stream_talk": bool(avatar.get("is_stream")),
        "timings": result.get("timings", {}),
    }


@app.get("/avatar", include_in_schema=False)
@app.get("/avatar/", include_in_schema=False)
def avatar_root():
    return get_avatar_info()


@app.get("/avatar/status/{talk_id}")
def get_avatar_status(talk_id: str):
    if not talk_id.startswith("tlk_") or not re.fullmatch(r"[A-Za-z0-9_-]+", talk_id):
        raise HTTPException(status_code=400, detail="A real D-ID talk ID is required.")

    try:
        from Avtar.DID_Servicee import DIDService

        did_service = DIDService()
        status_data = did_service.get_talk_status(talk_id)
        d_status = status_data.get("status")
        result_url = status_data.get("result_url")

        if d_status == "done":
            if not result_url:
                raise RuntimeError(f"D-ID completed talk {talk_id} without result_url.")
            local_filename = "response_avatar.mp4"
            local_path = AVATAR_DIR / local_filename

            # Re-use single output response_avatar.mp4
            # Concurrency protection: Only write if this is still the active or latest talk
            with active_talk_id_lock:
                should_save = (latest_active_talk_id is None or latest_active_talk_id == talk_id)

            if should_save:
                did_service.download_video(result_url, local_path)

            return {
                "status": "done",
                "talk_id": talk_id,
                "video_url": f"/avatar-files/{local_filename}?v={talk_id}",
            }
        elif d_status in ("error", "failed", "rejected"):
            raw_data = status_data.get("data") or {}
            raw_err = (
                raw_data.get("error")
                if isinstance(raw_data, dict)
                else raw_data
            ) or "Avatar generation failed."
            is_credit = "credit" in str(raw_err).lower()
            return {
                "status": "error",
                "talk_id": talk_id,
                "video_url": None,
                "error": "Insufficient D-ID credits" if is_credit else str(raw_err),
                "credit_exhausted": is_credit,
            }
        else:
            return {
                "status": "processing",
                "talk_id": talk_id,
                "video_url": None,
            }
    except Exception as error:
        print(f"[AVATAR ERROR] Error checking talk status for {talk_id}: {error}")
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve or validate D-ID talk {talk_id}: {error}",
        ) from error


@app.get("/avatar/info")
def get_avatar_info():
    from Avtar.avtar_config import get_avatar

    cfg = get_avatar()
    return {
        "image_url": cfg.get("browser_url", "/avatar-files/avtar_img.jpg"),
        "source_url": cfg.get("image_url"),
        "image_id": cfg.get("image_id"),
        "name": "Avtar",
    }


@app.get("/avatar/greeting")
def get_avatar_greeting(provider: Optional[str] = None):
    from Avtar.avtar_config import get_avatar
    from Avtar.LiveAvatarService import LiveAvatarService

    greeting_text = "Hi, I am your AI employee assistant. How can I help you today?"
    quick_options = [
        {"label": "📅 My attendance", "query": "Show my attendance"},
        {"label": "🌴 My leave balance", "query": "What is my leave balance?"},
        {"label": "👤 My profile", "query": "Show my complete employee profile details"},
    ]

    # HeyGen LiveAvatar Greeting: Return canonical audio & PCM without pre-rendered MP4 video
    if provider == "liveavatar":
        greeting_pcm_path = VOICE_DIR / "greeting_24k.pcm"
        greeting_audio_path = VOICE_DIR / "greeting.mp3"
        if not greeting_pcm_path.is_file() or not greeting_audio_path.is_file():
            try:
                get_assistant().tts_service.ensure_canonical_greeting(greeting_text)
            except Exception as e:
                print(f"[GREETING ENSURE NOTICE] {e}")
        greeting_pcm_b64 = None
        if greeting_pcm_path.is_file():
            try:
                import base64
                greeting_pcm_b64 = base64.b64encode(greeting_pcm_path.read_bytes()).decode("ascii")
            except Exception as e:
                print(f"[GREETING PCM B64 WARNING] {e}")
        return {
            "text": greeting_text,
            "audio_url": "/voice-files/greeting.mp3" if greeting_audio_path.is_file() else None,
            "pcm_url": "/voice-files/greeting_24k.pcm" if greeting_pcm_path.is_file() else None,
            "pcm_base64": greeting_pcm_b64,
            "video_url": None,
            "status": "ready",
            "provider": "liveavatar",
            "quick_options": quick_options,
        }

    cfg = get_avatar()
    is_custom = "custom_avatar" in cfg.get("browser_url", "")
    greeting_video_path = AVATAR_DIR / "greeting_avatar.mp4"

    # For default avatar without liveavatar provider, reuse pre-rendered greeting_avatar.mp4 for instant start
    if not is_custom and greeting_video_path.is_file() and greeting_video_path.stat().st_size > 10000:
        return {
            "text": greeting_text,
            "video_url": f"/avatar-files/{greeting_video_path.name}?v=greeting",
            "status": "ready",
            "talk_id": None,
            "quick_options": quick_options,
        }

    assistant_service = get_assistant()
    response_audio_path = VOICE_DIR / "ai_response.mp3"
    try:
        with assistant_service._audio_pipeline_lock, lock_response_audio(
            response_audio_path
        ):
            audio_path = assistant_service.tts_service.generate_speech(
                text=greeting_text,
                output_file=str(response_audio_path),
            )
            avatar = assistant_service.start_avatar(audio_path, greeting_text)
            if avatar.get("talk_id"):
                global latest_active_talk_id
                with active_talk_id_lock:
                    latest_active_talk_id = avatar["talk_id"]
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not generate the D-ID greeting: {error}",
        ) from error

    return {
        "text": greeting_text,
        "talk_id": avatar.get("talk_id"),
        "status": avatar.get("status", "idle"),
        "video_url": avatar.get("video_url"),
        "error": avatar.get("error"),
        "quick_options": [
            {"label": "📅 My attendance", "query": "Show my attendance"},
            {"label": "🌴 My leave balance", "query": "What is my leave balance?"},
            {"label": "👤 My profile", "query": "Show my complete employee profile details"},
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Real-time WebRTC Streaming Avatar Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/avatar/stream/new")
def create_avatar_stream():
    from Avtar.DID_Servicee import DIDService
    from Avtar.avtar_config import get_avatar

    cfg = get_avatar()
    source_url = cfg.get("image_url") or "https://d-id-public-bucket.s3.amazonaws.com/alice.jpg"
    try:
        did = DIDService()
        data = did.create_stream(source_url)
        return {
            "stream_id": data.get("id"),
            "session_id": data.get("session_id"),
            "offer": data.get("offer"),
            "ice_servers": data.get("ice_servers", []),
        }
    except Exception as err:
        return {"error": str(err), "stream_id": None}


@app.post("/avatar/stream/sdp")
def submit_avatar_stream_sdp(req: StreamSdpRequest):
    from Avtar.DID_Servicee import DIDService

    try:
        did = DIDService()
        res = did.send_stream_sdp(req.stream_id, req.answer, req.session_id)
        return {"success": True, "data": res}
    except Exception as err:
        return {"success": False, "error": str(err)}


@app.post("/avatar/stream/ice")
def submit_avatar_stream_ice(req: StreamIceRequest):
    from Avtar.DID_Servicee import DIDService

    try:
        did = DIDService()
        ok = did.send_stream_ice(
            req.stream_id,
            req.candidate,
            req.sdp_mid,
            req.sdp_mline_index,
            req.session_id,
        )
        return {"success": ok}
    except Exception as err:
        return {"success": False, "error": str(err)}


@app.post("/avatar/stream/talk")
def submit_avatar_stream_talk(req: StreamTalkRequest):
    from Avtar.DID_Servicee import DIDService

    try:
        did = DIDService()
        script = {}
        if req.audio_url:
            script = {"type": "audio", "audio_url": req.audio_url}
        elif req.text:
            script = {"type": "text", "input": req.text}
        res = did.talk_stream(req.stream_id, req.session_id, script)
        return {"success": True, "data": res}
    except Exception as err:
        return {"success": False, "error": str(err)}


@app.delete("/avatar/stream/{stream_id}")
def delete_avatar_stream(stream_id: str, session_id: str = ""):
    from Avtar.DID_Servicee import DIDService

    try:
        did = DIDService()
        did.close_stream(stream_id, session_id)
    except Exception:
        pass
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# HeyGen LiveAvatar WebRTC Streaming Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/avatar/live/session")
def create_live_avatar_session(req: Optional[LiveAvatarSessionRequest] = None):
    """
    Create a new HeyGen LiveAvatar session token for the frontend Web SDK.
    API_LIVE is kept securely on the server and never exposed to the client.
    """
    from Avtar.LiveAvatarService import LiveAvatarService

    try:
        service = LiveAvatarService()
        if not service.is_configured:
            raise HTTPException(
                status_code=503,
                detail="HeyGen LiveAvatar is not configured (API_LIVE is missing).",
            )

        kwargs = {}
        if req:
            if req.avatar_id:
                kwargs["avatar_id"] = req.avatar_id
            if req.mode:
                kwargs["mode"] = req.mode
            kwargs["is_sandbox"] = req.is_sandbox
            if req.quality:
                kwargs["quality"] = req.quality
            if req.language:
                kwargs["language"] = req.language
            if req.voice_id:
                kwargs["voice_id"] = req.voice_id
            if req.context_id:
                kwargs["context_id"] = req.context_id

        data = service.create_session_token(**kwargs)
        return {
            "success": True,
            "session_id": data.get("session_id"),
            "session_token": data.get("session_token"),
            "avatar_id": data.get("avatar_id"),
            "mode": data.get("mode"),
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re)) from re
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LiveAvatar session error: {exc}") from exc


@app.post("/avatar/live/start")
def start_live_avatar_session(req: LiveAvatarStartRequest):
    """
    Start the LiveAvatar session with session_token if started from backend.
    """
    from Avtar.LiveAvatarService import LiveAvatarService

    try:
        service = LiveAvatarService()
        data = service.start_session(req.session_token)
        return {"success": True, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/avatar/live/stop")
def stop_live_avatar_session(req: LiveAvatarStopRequest):
    """
    Clean up / stop an active LiveAvatar session.
    """
    from Avtar.LiveAvatarService import LiveAvatarService

    try:
        service = LiveAvatarService()
        ok = service.stop_session(req.session_token)
        return {"success": ok}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.get("/avatar/live/status")
def get_live_avatar_status():
    """
    Check if HeyGen LiveAvatar integration is configured and ready.
    """
    from Avtar.LiveAvatarService import LiveAvatarService

    service = LiveAvatarService()
    avatar_preview = "https://files2.heygen.ai/avatar/v3/582ee8fe072a48fda3bc68241aeff660_45660/preview_target.webp"
    return {
        "provider": "heygen_liveavatar",
        "configured": service.is_configured,
        "avatar_id": service.get_default_avatar_id(),
        "name": "Avtar",
        "preview_url": avatar_preview,
        "status": "ready" if service.is_configured else "not_configured",
    }



# ─────────────────────────────────────────────────────────────────────────────
# Custom Avatar Upload / Reset
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/avatar/upload")
async def upload_custom_avatar(image: UploadFile = File(...)):
    """
    Accept a user-supplied image, save it locally, upload it to D-ID, and
    update avtar_config.json so all future avatar talks use the new face.
    Returns the browser-accessible URL of the saved image.
    """
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{suffix}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    raw = await image.read()
    if len(raw) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds the 10 MB size limit.",
        )
    if len(raw) < 1024:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file appears to be empty or too small.",
        )

    local_filename = f"custom_avatar{suffix}"
    local_path = AVATAR_DIR / local_filename
    browser_url = f"/avatar-files/{local_filename}"
    staged_path = AVATAR_DIR / f".avatar-upload-{uuid4().hex}{suffix}"
    staged_path.write_bytes(raw)

    try:
        from Avtar.DID_Servicee import DIDService
        from Avtar.avtar_config import save_avatar

        did = DIDService()
        did_result = did.upload_image(str(staged_path))
        image_id = did_result.get("image_id") or ""
        image_url = did_result.get("image_url") or ""
        if not image_id or not image_url:
            raise RuntimeError("D-ID image upload returned no image ID or URL.")

        os.replace(staged_path, local_path)
        save_avatar(
            image_id=image_id,
            image_url=image_url,
            browser_url=browser_url,
        )
        return {
            "success": True,
            "browser_url": browser_url,
            "image_id": image_id,
            "image_url": image_url,
            "message": "Custom avatar uploaded and activated successfully.",
        }
    except Exception as did_err:
        raise HTTPException(
            status_code=502,
            detail=f"D-ID avatar image upload failed: {did_err}",
        ) from did_err
    finally:
        staged_path.unlink(missing_ok=True)


@app.post("/avatar/reset")
def reset_avatar():
    """Upload the built-in avatar image and activate its D-ID URL."""
    try:
        from Avtar.DID_Servicee import DIDService
        from Avtar.avtar_config import save_avatar

        image = DIDService().upload_image(str(AVATAR_DIR / "avtar_img.jpg"))
        if not image.get("image_id") or not image.get("image_url"):
            raise RuntimeError("D-ID image upload returned no image ID or URL.")
        save_avatar(
            image_id=image["image_id"],
            image_url=image["image_url"],
            browser_url="/avatar-files/avtar_img.jpg",
        )
        return {
            "success": True,
            "browser_url": "/avatar-files/avtar_img.jpg",
            "message": "Avatar reset to default.",
        }
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"Could not activate the default D-ID avatar: {err}") from err


@app.get("/avatar/custom-info")
def get_custom_avatar_info():
    """Return current avatar config including whether a custom avatar is active."""
    from Avtar.avtar_config import get_avatar

    cfg = get_avatar()
    browser_url = cfg["browser_url"]
    return {
        "browser_url": browser_url,
        "image_id": cfg["image_id"],
        "image_url": cfg["image_url"],
        "is_custom": "custom_avatar" in browser_url,
    }