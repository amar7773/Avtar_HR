from app.Services.Assistant import AssistantService


assistant = AssistantService()

text = "Hello, welcome to the AI Employee Assistant."

print("\n================================")
print("ASSISTANT AVATAR TEST")
print("================================")

result = assistant.generate_avatar(text)

print("\n================================")
print("AVATAR RESULT")
print("================================")

print("Audio File:")
print(result["audio_file"])

print("\nVideo File:")
print(result["video_file"])

print("\n================================")
print("TEST COMPLETED")
print("================================")