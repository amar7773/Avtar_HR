import os
import requests
from dotenv import load_dotenv

load_dotenv()
DID_API_KEY=os.getenv("API_DI_ID")
image_path="Avtar/assets/avtar_img.jpg"
with open(image_path,"rb") as image_file:
    response = requests.post(
        "https://api.d-id.com/images",
        headers={
            "Authorization": f"Basic {DID_API_KEY}"
        },
        files={
            "image": image_file
        }
    )
print("Status:", response.status_code)
print("Response:", response.text)