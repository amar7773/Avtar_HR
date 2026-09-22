import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
DID_API_KEY = os.getenv("API_DI_ID")
IMAGE_URL="https://img.magnific.com/premium-photo/graphic-designer-digital-avatar-generative-ai_934475-9292.jpg"

headers={
    "Authorization": f"Basic {DID_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "source_url": IMAGE_URL,
    "script": {
        "type": "text",
        "input": "Hello, welcome to the AI Employee Assistant."
    }
}
response = requests.post(
    "https://api.d-id.com/talks",
    headers=headers,
    json=payload
)
print("Create Status:", response.status_code)
print("Create Response:", response.text)

if response.status_code not in [200,201,200]:
    raise Exception("Talking avatar creation failed.")

talk_id=response.json()["id"]
print("Talk_ID :",talk_id)

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
        with open("Avtar/generated_avatar.mp4","wb") as vedio_file:
            vedio_file.write(vedio_response.content)
        print("\n✅ Video saved successfully:")
        print("Avtar/generated_avatar.mp4")
        break
    if data.get("status") == "error":
        print("\nError:")
        print(data)
        break