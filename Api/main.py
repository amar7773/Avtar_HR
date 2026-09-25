from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, Form
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.Services.Assistant import AssistantService
from app.Services.Auth import AuthService
from fastapi.staticfiles import StaticFiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = PROJECT_ROOT / "Voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

auth_service = AuthService()

app = FastAPI(
    title="AI Employee Assistant",
    description="AI Employee Assistant API",
    version="1.0.0"
)


app.mount(
    "/voice-files",
    StaticFiles(directory=str(VOICE_DIR)),
    name="voice-files"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


assistant = AssistantService()


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


@app.get("/")
def home():
    return {
        "message": "AI Employee Assistant API is running",
        "status": "success"
    }


@app.post("/login")
def login(request: LoginRequest):

    result = auth_service.login(request.employee_id)

    if not result["success"]:
        return result

    return result


@app.post("/chat")
def chat(request: ChatRequest):

    result = assistant.process(
        user_query=request.user_query,
        employee_id=request.employee_id
    )

    return result


@app.post("/tts")
def text_to_speech(request: TTSRequest):

    text = request.text.strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text is required."
        )

    audio_file = assistant.tts_service.generate_speech(
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

        text = assistant.stt_service.transcribe(
            str(input_audio_path)
        )

        return {
            "text": text
        }
    finally:
        input_audio_path.unlink(missing_ok=True)


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    employee_id: str = Form(...)
):

    input_audio_path = save_upload(audio)

    try:
        with input_audio_path.open("wb") as file:
            file.write(await audio.read())

        result = assistant.process_speech_to_speech(
            audio_file=str(input_audio_path),
            employee_id=employee_id
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        ) from error
    finally:
        input_audio_path.unlink(missing_ok=True)

    response_audio = result.get("response_audio")
    if not response_audio:
        raise HTTPException(
            status_code=502,
            detail="The voice assistant could not generate an audio response."
        )

    return {
        "user_text": result.get("user_query", ""),
        "response": result.get("response", ""),
        "audio_url": f"/voice-files/{Path(response_audio).name}"
    }