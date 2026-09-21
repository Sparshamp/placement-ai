# app/features/interview_simulation/stt.py
import tempfile, os, requests
from .config import WHISPER_SERVER_URL

def transcribe_uploaded_audio(raw_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(raw_bytes)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                f"{WHISPER_SERVER_URL}/transcribe",
                files={"file": f},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()
    finally:
        os.unlink(tmp_path)

def check_whisper_server():
    resp = requests.get(f"{WHISPER_SERVER_URL}/health", timeout=5)
    resp.raise_for_status()