# app/features/interview_simulation/tts.py
import edge_tts
import tempfile, os
from .config import TTS_VOICE, TTS_RATE, TTS_PITCH

async def synthesize(text: str) -> bytes:
    if not text or not text.strip():
        return b""
    communicate = edge_tts.Communicate(text, voice=TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name
    try:
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except PermissionError:
            pass