import json
import os

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "avatar_config.json")
DEFAULT_IMAGE_URL = (
    "https://img.magnific.com/premium-photo/"
    "graphic-designer-digital-avatar-generative-ai_934475-9292.jpg"
)


def save_avatar(image_id, image_url):
    data = {"image_id": image_id, "image_url": image_url}
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def get_avatar():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    image_url = os.getenv("AVATAR_IMAGE_URL", DEFAULT_IMAGE_URL)
    return {"image_id": None, "image_url": image_url}


def get_avtar():
    """Backward-compatible alias for callers using the old function name."""
    return get_avatar()
