import json
import os

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILES = [
    os.path.join(BASE_DIR, "avtar_config.json"),
    os.path.join(BASE_DIR, "avatar_config.json"),
]
DEFAULT_IMAGE_URL = (
    "https://img.magnific.com/premium-photo/"
    "graphic-designer-digital-avatar-generative-ai_934475-9292.jpg"
)


def get_config_file_path():
    for path in CONFIG_FILES:
        if os.path.exists(path):
            return path
    return CONFIG_FILES[0]


def save_avatar(image_id, image_url, browser_url="/avatar-files/avtar_img.jpg"):
    data = {
        "image_id": image_id,
        "image_url": image_url,
        "browser_url": browser_url,
    }
    config_file = get_config_file_path()
    with open(config_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def get_avatar():
    browser_url = "/avatar-files/avtar_img.jpg"
    for config_file in CONFIG_FILES:
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if isinstance(data, dict):
                        if not data.get("browser_url"):
                            data["browser_url"] = browser_url
                        return data
            except Exception:
                continue

    image_url = os.getenv("AVATAR_IMAGE_URL", DEFAULT_IMAGE_URL)
    return {
        "image_id": None,
        "image_url": image_url,
        "browser_url": browser_url,
    }


def get_avtar():
    """Backward-compatible alias for callers using the old function name."""
    return get_avatar()
