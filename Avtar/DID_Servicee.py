import os
import time
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
        payload = {
            "source_url": image_url,
            "script": {"type": "audio", "audio_url": audio_url},
            "config": {
                "stitch": True,
                "fluent": True,
                "pad_audio": 0.0,
            },
        }
        response = requests.post(
            f"{self.base_url}/talks",
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(
                f"Talking avatar creation failed: {response.text}"
            )
        return response.json()["id"]

    @staticmethod
    def composite_full_avatar(face_video_path, output_video_path, source_img_path=None, original_audio_path=None):
        import subprocess
        if not source_img_path:
            source_img_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "avtar_img.jpg"
            )
        if not os.path.exists(source_img_path) or not os.path.exists(face_video_path):
            return face_video_path

        if original_audio_path and os.path.exists(original_audio_path):
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", source_img_path,
                "-i", face_video_path,
                "-i", original_audio_path,
                "-filter_complex", "[1:v]scale=1142:1142[face];[0:v][face]overlay=920:114:shortest=1[outv]",
                "-map", "[outv]", "-map", "2:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
                output_video_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", source_img_path,
                "-i", face_video_path,
                "-filter_complex", "[1:v]scale=1142:1142[face];[0:v][face]overlay=920:114:shortest=1[outv]",
                "-map", "[outv]", "-map", "1:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
                output_video_path
            ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_video_path
        except Exception as e:
            print(f"[AVATAR WARNING] FFmpeg compositing failed: {e}")
            return face_video_path
    def get_talk_status(self, talk_id):
        response = requests.get(
            f"{self.base_url}/talks/{talk_id}",
            headers=self.headers,
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to check avatar status: {response.text}"
            )
        data = response.json()
        status = data.get("status")
        result_url = data.get("result_url")
        return {
            "talk_id": talk_id,
            "status": status,
            "result_url": result_url,
            "data": data,
        }

    def start_talking_avatar_from_audio(self, image_url, audio_path):
        audio_url = self.upload_audio(audio_path)["url"]
        talk_id = self.create_talking_avatar(
            image_url=image_url,
            audio_url=audio_url
        )
        return {
            "talk_id": talk_id,
            "audio_url": audio_url,
            "status": "processing",
        }

    def wait_for_video(self, talk_id, timeout=120, interval=3):
        start_time = time.time()
        while time.time() - start_time < timeout:
            data_info = self.get_talk_status(talk_id)
            status = data_info.get("status")
            print("🎭 D-ID Avatar Status:", status)
            print("🎭 D-ID Response:", data_info.get("data"))

            if status == "done":
                result_url = data_info.get("result_url")
                if result_url:
                    print("🎬 Avatar Video URL:", result_url)
                    return result_url
                raise RuntimeError(
                    f"D-ID completed but no result_url was returned. "
                    f"Response: {data_info.get('data')}"
                )
            if status in ("error", "failed"):
                raise RuntimeError(
                    f"D-ID avatar generation failed: {data_info.get('data')}"
                )
            time.sleep(interval)
        raise TimeoutError(
            f"D-ID avatar generation timed out for talk_id={talk_id}"
        )

    def generate_avatar_from_audio(self, image_url, audio_path):
        talk_info = self.start_talking_avatar_from_audio(
            image_url=image_url,
            audio_path=audio_path,
        )
        video_url = self.wait_for_video(talk_info["talk_id"])
        return {
            "talk_id": talk_info["talk_id"],
            "audio_url": talk_info["audio_url"],
            "video_url": video_url,
        }
