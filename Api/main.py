from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.Services.Assistant import AssistantService
from app.Services.Auth import AuthService

auth_service=AuthService()

app = FastAPI(
    title="AI Employee Assistant",
    description="AI Employee Assistant API",
    version="1.0.0"
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
    employee_id: int

class ChatRequest(BaseModel):
    user_query: str
    employee_id: int


class TTSRequest(BaseModel):
    text: str


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

    audio_file = assistant.tts_service.generate_speech(
        text=request.text,
        output_file="Voice/api_response.mp3"
    )

    return {
        "text": request.text,
        "audio_file": audio_file
    }


@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):

    input_audio_path = f"Voice/{audio.filename}"

    with open(input_audio_path, "wb") as file:
        file.write(await audio.read())

    text = assistant.stt_service.transcribe(
        input_audio_path
    )

    return {
        "text": text,
        "audio_file": input_audio_path
    }


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    employee_id: int = Form(...)
):

    input_audio_path = f"Voice/{audio.filename}"

    with open(input_audio_path, "wb") as file:
        file.write(await audio.read())

    result = assistant.process_speech_to_speech(
        audio_file=input_audio_path,
        employee_id=employee_id
    )

    response_audio = result.get("response_audio")

    return FileResponse(
        path=response_audio,
        media_type="audio/mpeg",
        filename="ai_response.mp3"
    )