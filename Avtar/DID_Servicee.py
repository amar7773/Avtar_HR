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

    def upload_image(self, image_path):
        """Upload a local image file to D-ID /images and return image_id + image_url."""
        import mimetypes
        filename = os.path.basename(image_path)
        mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        with open(image_path, "rb") as img_file:
            response = requests.post(
                f"{self.base_url}/images",
                headers=self.headers,
                files={"image": (filename, img_file, mime_type)},
                timeout=60,
            )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Image upload to D-ID failed: {response.text}")
        data = response.json()
        return {
            "image_id": data.get("id"),
            "image_url": data.get("url"),
        }

    def upload_audio(self, audio_path):
        filename = os.path.basename(audio_path)
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                f"{self.base_url}/audios",
                headers=self.headers,
                files={"audio": (filename, audio_file, "audio/mpeg")},
                timeout=60,
            )
        if response.status_code != 201:
            raise RuntimeError(f"Audio upload failed: {response.text}")
        data = response.json()
        return {"url": data["url"]}

    def create_talking_avatar(self, image_url, audio_url, expression="neutral"):
        valid_expressions = ("neutral", "happy", "serious", "surprise")
        chosen_expression = expression if expression in valid_expressions else "neutral"

        config = {
            "stitch": True,
            "fluent": True,
            "pad_audio": 0.0,
            "driver_expressions": {
                "expressions": [
                    {
                        "start_frame": 0,
                        "expression": chosen_expression,
                        "intensity": 0.85,
                    }
                ],
                "transition_frames": 20,
            },
        }

        payload = {
            "source_url": image_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url,
            },
            "config": config,
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
        import shutil
        if not source_img_path:
            source_img_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "avtar_img.jpg"
            )
        if not os.path.exists(face_video_path):
            return face_video_path

        # Check if the D-ID output video is already full-frame (stitched)
        is_full_frame = False
        try:
            cmd_probe = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                face_video_path
            ]
            res = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
            dims = res.stdout.strip().replace("x", " ").split()
            if len(dims) >= 2:
                vw = int(dims[0])
                vh = int(dims[1])
                # D-ID with stitch=True scales to 1280x854 (aspect ratio 1.5) or full frame
                if vw >= 1000 or (vw != vh and vw > 600) or abs(vw / vh - 1.5) < 0.2:
                    is_full_frame = True
        except Exception as probe_err:
            print(f"[AVATAR INFO] Dimension probe info: {probe_err}")
            # If probe fails, D-ID requested with stitch=True is full-frame
            is_full_frame = True

        # D-ID with stitch=True natively generates the seamless stitched video.
        # Preserve D-ID's native output directly to guarantee natural lip-sync, expression and facial integrity.
        try:
            if os.path.abspath(face_video_path) != os.path.abspath(output_video_path):
                shutil.copy2(face_video_path, output_video_path)
            return output_video_path
        except Exception as e:
            print(f"[AVATAR WARNING] Video copy fallback: {e}")
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

    def start_talking_avatar_from_audio(self, image_url, audio_path, expression="neutral"):
        audio_url = self.upload_audio(audio_path)["url"]
        talk_id = self.create_talking_avatar(
            image_url=image_url,
            audio_url=audio_url,
            expression=expression,
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

            if status == "done":
                result_url = data_info.get("result_url")
                if result_url:
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
