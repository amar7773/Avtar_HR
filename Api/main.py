import os
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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
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
        raise HTTPException(
            status_code=502,
            detail=str(error),
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

    try:
        rel_audio_path = Path(response_audio).resolve().relative_to(VOICE_DIR.resolve()).as_posix()
    except Exception:
        rel_audio_path = Path(response_audio).name

    return {
        "mode": result.get("mode", mode),
        "language": result.get("language", "English"),
        "user_text": result.get("user_query", ""),
        "response": result.get("response", ""),
        "audio_url": f"/voice-files/{rel_audio_path}",
        "avatar": avatar,
        "avatar_status": avatar.get("status", "idle"),
        "avatar_talk_id": avatar.get("talk_id"),
        "avatar_video_url": avatar.get("video_url"),
    }


@app.get("/avatar", include_in_schema=False)
@app.get("/avatar/", include_in_schema=False)
def avatar_root():
    return get_avatar_info()


@app.get("/avatar/status")
@app.get("/avatar/status/")
@app.get("/avatar/status/{talk_id}")
def get_avatar_status(talk_id: str = "latest"):
    if not talk_id or talk_id.strip() in ("", "None", "null"):
        talk_id = "latest"

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
            raw_err = status_data.get("data", {}).get("error") or "Avatar generation failed."
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
    custom_video_path = AVATAR_DIR / "greeting_custom_avatar.mp4"
    greeting_audio_path = VOICE_DIR / "greeting.mp3"

    if not greeting_audio_path.exists():
        try:
            get_assistant().tts_service.generate_speech(
                text=greeting_text,
                output_file=str(greeting_audio_path),
            )
        except Exception as error:
            print(f"[GREETING ERROR] TTS audio generation failed: {error}")

    from Avtar.avtar_config import get_avatar
    cfg = get_avatar()
    browser_url = cfg.get("browser_url", "/avatar-files/avtar_img.jpg")
    is_custom = "custom_avatar" in browser_url

    video_url = None
    talk_id = None

    if is_custom:
        if custom_video_path.exists() and custom_video_path.stat().st_size > 10000:
            video_url = f"/avatar-files/{custom_video_path.name}"
        else:
            # Initiate D-ID talk for custom avatar greeting using ElevenLabs audio
            image_url = cfg.get("image_url")
            if image_url and greeting_audio_path.exists():
                try:
                    from Avtar.DID_Servicee import DIDService
                    did = DIDService()
                    talk_res = did.start_talking_avatar_from_audio(
                        image_url=image_url,
                        audio_path=str(greeting_audio_path),
                        expression="happy",
                    )
                    talk_id = talk_res.get("talk_id")
                    if talk_id:
                        get_assistant()._latest_avatar_status = {
                            "talk_id": talk_id,
                            "status": "processing",
                            "video_url": None,
                            "is_greeting": True,
                        }
                except Exception as did_err:
                    print(f"[GREETING D-ID INFO] Custom avatar D-ID talk initiation: {did_err}")
    else:
        if greeting_video_path.exists() and greeting_video_path.stat().st_size > 10000:
            video_url = f"/avatar-files/{greeting_video_path.name}"

    return {
        "text": greeting_text,
        "audio_url": (
            f"/voice-files/{greeting_audio_path.name}"
            if greeting_audio_path.exists()
            else None
        ),
        "video_url": video_url,
        "talk_id": talk_id,
        "browser_url": browser_url,
        "is_custom": is_custom,
        "status": "ready" if (video_url or greeting_audio_path.exists()) else "processing",
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

    # Persist locally so it is served via /avatar-files/
    local_filename = f"custom_avatar{suffix}"
    local_path = AVATAR_DIR / local_filename
    try:
        local_path.write_bytes(raw)
    except Exception as save_err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save image: {save_err}",
        ) from save_err

    # Clean up old custom greeting video if present
    custom_greeting = AVATAR_DIR / "greeting_custom_avatar.mp4"
    if custom_greeting.exists():
        try:
            custom_greeting.unlink(missing_ok=True)
        except Exception:
            pass

    browser_url = f"/avatar-files/{local_filename}"

    # Upload to D-ID and update config
    try:
        from Avtar.DID_Servicee import DIDService
        from Avtar.avtar_config import save_avatar

        did = DIDService()
        did_result = did.upload_image(str(local_path))
        image_id = did_result.get("image_id") or ""
        image_url = did_result.get("image_url") or ""

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
        # D-ID upload failed — still serve the locally saved image for the UI,
        # but fall back to the existing D-ID image_url for lip-sync generation.
        print(f"[AVATAR UPLOAD] D-ID upload failed, using local file only: {did_err}")
        try:
            from Avtar.avtar_config import get_avatar, save_avatar
            existing = get_avatar()
            save_avatar(
                image_id=existing.get("image_id", ""),
                image_url=existing.get("image_url", ""),
                browser_url=browser_url,
            )
        except Exception:
            pass
        return {
            "success": True,
            "browser_url": browser_url,
            "image_id": None,
            "image_url": None,
            "warning": f"Image saved locally but D-ID upload failed: {did_err}. Lip-sync will use the previous D-ID image.",
        }


@app.post("/avatar/reset")
def reset_avatar():
    """Reset the avatar back to the built-in default."""
    try:
        from Avtar.avtar_config import save_avatar

        custom_greeting = AVATAR_DIR / "greeting_custom_avatar.mp4"
        if custom_greeting.exists():
            try:
                custom_greeting.unlink(missing_ok=True)
            except Exception:
                pass

        default_image_id = os.getenv("DEFAULT_AVATAR_IMAGE_ID", "")
        default_image_url = os.getenv("DEFAULT_AVATAR_IMAGE_URL", "")
        save_avatar(
            image_id=default_image_id,
            image_url=default_image_url,
            browser_url="/avatar-files/avtar_img.jpg",
        )
        return {
            "success": True,
            "browser_url": "/avatar-files/avtar_img.jpg",
            "message": "Avatar reset to default.",
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.get("/avatar/custom-info")
def get_custom_avatar_info():
    """Return current avatar config including whether a custom avatar is active."""
    try:
        from Avtar.avtar_config import get_avatar

        cfg = get_avatar()
        browser_url = cfg.get("browser_url", "/avatar-files/avtar_img.jpg")
        is_custom = "custom_avatar" in browser_url
        return {
            "browser_url": browser_url,
            "image_id": cfg.get("image_id"),
            "image_url": cfg.get("image_url"),
            "is_custom": is_custom,
        }
    except Exception as err:
        return {
            "browser_url": "/avatar-files/avtar_img.jpg",
            "image_id": None,
            "image_url": None,
            "is_custom": False,
            "error": str(err),
        }