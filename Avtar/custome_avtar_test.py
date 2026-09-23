from Avtar.DID_Servicee import DIDService
from Avtar.avtar_config import get_avtar
import time
import requests


did = DIDService()


# --------------------------------
# 1. Get current avatar
# --------------------------------

avatar = get_avtar()

if not avatar:
    raise Exception("No avatar configured.")

image_url = avatar["image_url"]

print("Current Avatar:")
print(avatar["image_id"])


# --------------------------------
# 2. Existing ElevenLabs audio
# --------------------------------

audio_file = "Voice/api_response.mp3"


# --------------------------------
# 3. Create talking avatar
# --------------------------------

result = did.generate_avatar_from_audio(
    image_url=image_url,
    audio_path=audio_file
)

talk_id = result["talk_id"]

print("\nTalking Avatar Created")
print("Talk ID:")
print(talk_id)


# --------------------------------
# 4. Wait for video
# --------------------------------

while True:

    time.sleep(5)

    data = did.get_talk_status(talk_id)

    status = data.get("status")

    print("Avatar Status:", status)

    if status == "done":

        video_url = data.get("result_url")

        print("\n================================")
        print("AVATAR READY")
        print("================================")

        print("Video URL:")
        print(video_url)

        # Download video
        video_response = requests.get(video_url)

        if video_response.status_code != 200:
            raise Exception("Video download failed.")

        output_file = "Avtar/full_conversation_avatar.mp4"

        with open(output_file, "wb") as video_file:
            video_file.write(video_response.content)

        print("\n✅ Video saved:")
        print(output_file)

        break


    elif status == "error":

        print("\n❌ Avatar generation failed:")
        print(data)

        break