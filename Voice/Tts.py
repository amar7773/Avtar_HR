import os
import asyncio
import edge_tts


class TTSService:

    def __init__(self):
        self.voice = "en-IN-PrabhatNeural"

    def generate_speech(
        self,
        text,
        output_file="Voice/ai_response.mp3"
    ):
        if not text or not str(text).strip():
            raise ValueError("Text is required for TTS.")

        text = str(text).strip()

        os.makedirs(
            os.path.dirname(output_file) or ".",
            exist_ok=True
        )

        try:
            loop = asyncio.get_running_loop()

        except RuntimeError:
            asyncio.run(
                self._generate(
                    text,
                    output_file
                )
            )

        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=1
            ) as executor:

                future = executor.submit(
                    asyncio.run,
                    self._generate(
                        text,
                        output_file
                    )
                )

                future.result()

        return output_file

    async def _generate(
        self,
        text,
        output_file
    ):
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate="+5%"
        )

        await communicate.save(output_file)