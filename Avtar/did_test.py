import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Avtar.DID_Servicee import DIDService


if __name__ == "__main__":
    image_path = Path(__file__).resolve().parent / "avtar_img.jpg"
    result = DIDService().upload_image(str(image_path))
    print(f"Image upload succeeded: image_id={result['image_id']}")
    print(f"D-ID image URL: {result['image_url']}")
