import hashlib
from pathlib import Path

from Avtar.DID_Servicee import DIDService
from Avtar.avtar_config import get_avatar
from Voice.Tts import TTSService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIO_FILE = PROJECT_ROOT / "Voice" / "ai_response.mp3"
VIDEO_FILE = PROJECT_ROOT / "Avtar" / "did_lipsync_test.mp4"
TEST_RESPONSE = (
    "Great news. This is the current response for verifying D-ID lip-sync "
    "and a happy facial reaction."
)


def main():
    tts = TTSService()
    generated_audio = Path(
        tts.generate_speech(TEST_RESPONSE, output_file=str(AUDIO_FILE))
    ).resolve()
    if generated_audio != AUDIO_FILE.resolve():
        raise RuntimeError(f"TTS wrote to an unexpected path: {generated_audio}")
    audio_hash = tts.validate_generated_speech(TEST_RESPONSE, AUDIO_FILE)
    print(f"Validated canonical response audio: {AUDIO_FILE} ({audio_hash})")

    avatar = get_avatar()
    image_url = avatar.get("image_url")
    if not image_url:
        raise ValueError("No active D-ID avatar image is configured.")

    did = DIDService()
    talk = did.start_talking_avatar_from_audio(
        image_url=image_url,
        audio_path=str(AUDIO_FILE),
        expression=did.expression_for_response(TEST_RESPONSE),
    )
    if talk["audio_sha256"] != audio_hash:
        raise RuntimeError("The D-ID upload did not match the current response MP3.")

    talk_id = talk["talk_id"]
    print(f"D-ID talk ID: {talk_id}")
    result_url = did.wait_for_video(talk_id)
    did.download_video(result_url, VIDEO_FILE)
    video_hash = hashlib.sha256(VIDEO_FILE.read_bytes()).hexdigest()
    print(f"Validated D-ID MP4: {VIDEO_FILE} ({video_hash})")
    print("The MP4 contains D-ID-generated audio and video; no audio replacement was applied.")


if __name__ == "__main__":
    main()
