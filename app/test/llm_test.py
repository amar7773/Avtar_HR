from app.Services.Assistant import AssistantService
from Voice.Microphone import record_audio


assistant = AssistantService()

audio_file = record_audio(duration=5)

result = assistant.process_voice(
    audio_file=audio_file,
    employee_id=101
)

print("\n==============================")
print("USER SAID:")
print(result["user_query"])

print("\nINTENT:")
print(result["intent"])

print("\nCONFIDENCE:")
print(result["confidence"])

print("\nAI RESPONSE:")
print(result["response"])

print("\nERROR:")
print(result.get("error"))

print("==============================")