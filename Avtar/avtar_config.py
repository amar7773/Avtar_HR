import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse


CONFIG_FILE = Path(__file__).resolve().parent / "avtar_config.json"
DEFAULT_BROWSER_URL = "/avatar-files/avtar_img.jpg"


def _validate_image_url(image_url):
    parsed = urlparse(image_url or "")
    if parsed.scheme not in ("https", "s3") or not parsed.netloc:
        raise ValueError("Avatar image URL must be HTTPS or a D-ID S3 URL.")
    return image_url


def save_avatar(image_id, image_url, browser_url=DEFAULT_BROWSER_URL):
    if not image_id or not image_url:
        raise ValueError("D-ID avatar image ID and URL are required.")
    data = {
        "image_id": image_id,
        "image_url": _validate_image_url(image_url),
        "browser_url": browser_url or DEFAULT_BROWSER_URL,
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".avtar_config.", suffix=".tmp", dir=str(CONFIG_FILE.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as config_file:
            json.dump(data, config_file, indent=4)
            config_file.flush()
            os.fsync(config_file.fileno())
        os.replace(temporary_name, CONFIG_FILE)
    except Exception:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
        raise


def get_avatar():
    if not CONFIG_FILE.is_file():
        raise FileNotFoundError(f"Required avatar configuration is missing: {CONFIG_FILE}")
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {CONFIG_FILE.name}: {error}") from error
    if (
        not isinstance(data, dict)
        or not data.get("image_id")
        or not data.get("image_url")
    ):
        raise ValueError(f"{CONFIG_FILE.name} must define image_id and image_url.")
    data["image_url"] = _validate_image_url(data["image_url"])
    data.setdefault("browser_url", DEFAULT_BROWSER_URL)
    return data
