import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
DID_API_KEY =os.getenv("API_DI_ID")
IMAGE_URL = (
    "s3://d-id-images-prod/"
    "google-oauth2|113587619454688211094/"
    "img_pDEPifk2LR46TtqPo8UeU/"
    "avtar_img.jpg"
)
AUDIO_FILE="Voice/api_response.mp3"

with open(AUDIO_FILE,"rb") as audio_file:
    response=requests.post(
        "https://api.d-id.com/audios",
        headers={
            "Authorization":f"Basic {DID_API_KEY}"
        },
        files={
            "audio":audio_file
        }
    )
print("Audio Upload Status:", response.status_code)
if response.status_code != 201:
    print(response.text)
    raise Exception("Audio upload failed.")
audio_data=response.json()
audio_url=audio_data["url"]
print("Audio URL:")
print(audio_url)
payload={
    "source_url":IMAGE_URL,
    "script":{
        "type":"audio",
        "audio_url":audio_url
    }
}
response=requests.post(
    "https://api.d-id.com/talks",
    headers={
        "Authorization": f"Basic {DID_API_KEY}",
        "Content-Type": "application/json"
    },
    json=payload
)
print("\nTalk Creation Status:", response.status_code)
print(response.text)
if response.status_code not in [200, 201, 202]:
    raise Exception("Avatar creation failed.")
talk_id = response.json()["id"]
print("\nTalk ID:", talk_id)

while True:
    time.sleep(5)
    status_response=requests.get(
        f"https://api.d-id.com/talks/{talk_id}",
        headers={
            "Authorization": f"Basic {DID_API_KEY}"
        })
    data = status_response.json()

    print("Status:", data.get("status"))

    if data.get("status")=="done":
        vedio_url=data.get("result_url")
        print("vedio_url:")
        print(vedio_url)
        vedio_response=requests.get(vedio_url)
        if vedio_response.status_code != 200:
            raise Exception("Video download failed.")
        with open("Avtar/generated_avatar.mp4","wb") as vedio_file:
            vedio_file.write(vedio_response.content)
        print("\n✅ Video saved successfully:")
        print("Avtar/generated_avatar.mp4")
        break
    if data.get("status") == "error":
        print("\nError:")
        print(data)
        break