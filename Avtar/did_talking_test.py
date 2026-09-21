import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
DID_API_KEY = os.getenv("API_DI_ID")
IMAGE_URL="https://img.magnific.com/premium-photo/human-male-avatar_930095-1312.jpg"

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

    if data.get("status") == "done":
        print("\nVideo URL:")
        print(data.get("result_url"))
        break
    if data.get("status") == "error":
        print("\nError:")
        print(data)
        break