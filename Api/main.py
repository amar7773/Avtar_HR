import sys
from pathlib import Path
from uuid import uuid4

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

from fastapi import FastAPI, UploadFile, File, Form
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from threading import Lock


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


class TTSRequest(BaseModel):
    text: str


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


@app.post("/login")
def login(request: LoginRequest):

    result = get_auth_service().login(request.employee_id)

    if not result["success"]:
        return result

    return result


@app.post("/chat")
def chat(request: ChatRequest):

    result = get_assistant().process(
        user_query=request.user_query,
        employee_id=request.employee_id
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

    audio_file = get_assistant().tts_service.generate_speech(
        text=text,
        output_file=str(VOICE_DIR / "api_response.mp3")
    )

    return FileResponse(
        path=audio_file,
        media_type="audio/mpeg",
        filename="ai_response.mp3"
    )


@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):

    input_audio_path = save_upload(audio)

    try:
        with input_audio_path.open("wb") as file:
            file.write(await audio.read())

        text = get_assistant().stt_service.transcribe(
            str(input_audio_path)
        )

        return {
            "text": text
        }
    finally:
        safe_unlink(input_audio_path)


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    employee_id: str = Form(...),
    mode: str = Form(default="avatar_mode")
):

    input_audio_path = save_upload(audio)

    try:
        with input_audio_path.open("wb") as file:
            file.write(await audio.read())

        result = get_assistant().process_speech_to_speech(
            audio_file=str(input_audio_path),
            employee_id=employee_id,
            mode=mode
        )
    except Exception as error:
        print("[VOICE ERROR]:", error)
        raise HTTPException(
        status_code=502,
        detail=str(error)
        ) from error
    finally:
        safe_unlink(input_audio_path)

    response_audio = result.get("response_audio")
    if not response_audio:
        raise HTTPException(
            status_code=502,
            detail="The voice assistant could not generate an audio response."
        )
    avatar = result.get("avatar") or {}
    return {
        "mode": result.get("mode", mode),
        "language": result.get("language", "English"),
        "user_text": result.get("user_query", ""),
        "response": result.get("response", ""),
        "audio_url": f"/voice-files/{Path(response_audio).name}",
        "avatar": avatar,
        "avatar_status": avatar.get("status", "idle"),
        "avatar_talk_id": avatar.get("talk_id"),
        "avatar_video_url": avatar.get("video_url"),
    }


@app.get("/avatar/status/{talk_id}")
def get_avatar_status(talk_id: str):
    if not talk_id or talk_id.strip() in ("", "None", "null"):
        return {
            "status": "error",
            "talk_id": talk_id,
            "video_url": None,
            "error": "Invalid talk ID.",
        }

    if talk_id == "latest":
        latest = getattr(get_assistant(), "_latest_avatar_status", None)
        if not latest:
            return {"status": "idle", "talk_id": None, "video_url": None}
        if not latest.get("talk_id"):
            return latest
        talk_id = latest["talk_id"]

    try:
        from Avtar.DID_Servicee import DIDService

        did_service = DIDService()
        status_data = did_service.get_talk_status(talk_id)
        d_status = status_data.get("status")
        result_url = status_data.get("result_url")

        if d_status == "done":
            video_url = result_url
            if result_url:
                try:
                    local_filename = f"talk_{talk_id}.mp4"
                    local_path = AVATAR_DIR / local_filename
                    if not local_path.exists():
                        import requests
                        temp_path = AVATAR_DIR / f"temp_{talk_id}.mp4"
                        r = requests.get(result_url, timeout=30)
                        if r.status_code == 200:
                            temp_path.write_bytes(r.content)
                            did_service.composite_full_avatar(
                                str(temp_path),
                                str(local_path),
                            )
                            temp_path.unlink(missing_ok=True)
                    if local_path.exists() and local_path.stat().st_size > 10000:
                        video_url = f"/avatar-files/{local_filename}"
                except Exception as comp_err:
                    print(f"[AVATAR WARNING] Full-frame composite skipped: {comp_err}")

            return {
                "status": "done",
                "talk_id": talk_id,
                "video_url": video_url,
            }
        elif d_status in ("error", "failed"):
            return {
                "status": "error",
                "talk_id": talk_id,
                "video_url": None,
                "error": status_data.get("data", {}).get("error")
                or "Avatar generation failed.",
            }
        else:
            return {
                "status": "processing",
                "talk_id": talk_id,
                "video_url": None,
            }
    except Exception as error:
        print(f"[AVATAR ERROR] Error checking talk status for {talk_id}: {error}")
        return {
            "status": "error",
            "talk_id": talk_id,
            "video_url": None,
            "error": str(error),
        }


@app.get("/avatar/info")
def get_avatar_info():
    try:
        from Avtar.avtar_config import get_avatar

        cfg = get_avatar()
        return {
            "image_url": cfg.get("browser_url", "/avatar-files/avtar_img.jpg"),
            "source_url": cfg.get("image_url"),
            "image_id": cfg.get("image_id"),
            "name": "Avtar",
        }
    except Exception:
        return {
            "image_url": "/avatar-files/avtar_img.jpg",
            "name": "Avtar",
        }


@app.get("/avatar/greeting")
def get_avatar_greeting():
    greeting_text = "Hi, I'm your AI employee assistant. How can I help you today?"
    greeting_video_path = AVATAR_DIR / "greeting_avatar.mp4"
    greeting_audio_path = VOICE_DIR / "greeting.mp3"

    if not greeting_audio_path.exists():
        try:
            get_assistant().tts_service.generate_speech(
                text=greeting_text,
                output_file=str(greeting_audio_path),
            )
        except Exception as error:
            print(f"[GREETING ERROR] TTS audio generation failed: {error}")

    has_video = (
        greeting_video_path.exists()
        and greeting_video_path.stat().st_size > 10000
    )

    return {
        "text": greeting_text,
        "audio_url": (
            f"/voice-files/{greeting_audio_path.name}"
            if greeting_audio_path.exists()
            else None
        ),
        "video_url": (
            f"/avatar-files/{greeting_video_path.name}"
            if has_video
            else None
        ),
        "status": "ready",
    }