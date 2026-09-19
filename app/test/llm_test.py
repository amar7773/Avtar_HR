from app.Services.Assistant import AssistantService
from Voice.Microphone import record_audio


assistant = AssistantService()


print("\n======================================")
print("      SPEECH TO SPEECH TEST")
print("======================================")


# Step 1 — Record user voice

audio_file = record_audio(
    filename="Voice/user_input.wav",
    duration=7
)


# Step 2 — Voice → AI → Voice

result = assistant.process_speech_to_speech(
    audio_file=audio_file,
    employee_id=101
)


# Step 3 — Display result

print("\n🎤 USER SAID:")
print(result["user_query"])


print("\n🧠 INTENT:")
print(result["intent"])


print("\n🔎 ENTITIES:")
print(result["entities"])


print("\n🔧 TOOL USED:")
print(result["tool_used"])


print("\n🤖 AI RESPONSE:")
print(result["response"])


print("\n🔊 RESPONSE AUDIO:")
print(result["response_audio"])


print("\n======================================")