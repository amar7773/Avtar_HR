import os

import requests
from dotenv import load_dotenv


load_dotenv()


class DIDService:
    def __init__(self):
        self.api_key = os.getenv("API_DI_ID")
        if not self.api_key:
            raise ValueError("API_DI_ID not found in .env")
        self.base_url = "https://api.d-id.com"
        self.headers = {"Authorization": f"Basic {self.api_key}"}

    def upload_audio(self, audio_path):
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                f"{self.base_url}/audios",
                headers=self.headers,
                files={"audio": audio_file},
                timeout=60,
            )
        if response.status_code != 201:
            raise RuntimeError(f"Audio upload failed: {response.text}")
        data = response.json()
        return {"url": data["url"]}

    def create_talking_avatar(self, image_url, audio_url):
        response = requests.post(
            f"{self.base_url}/talks",
            headers={**self.headers, "Content-Type": "application/json"},
            json={
                "source_url": image_url,
                "script": {"type": "audio", "audio_url": audio_url},
            },
            timeout=60,
        )
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(
                f"Talking avatar creation failed: {response.text}"
            )
        return response.json()["id"]

    def generate_avatar_from_audio(self, image_url, audio_path):
        audio_url = self.upload_audio(audio_path)["url"]
        talk_id = self.create_talking_avatar(image_url, audio_url)
        return {"talk_id": talk_id, "audio_url": audio_url}
