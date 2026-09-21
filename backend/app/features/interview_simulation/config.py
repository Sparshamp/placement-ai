# app/features/interview_simulation/config.py
WHISPER_SERVER_URL = "http://127.0.0.1:8000"

#OLLAMA_BASE_URL = "http://10.1.12.31:11434"   # adjust to your GPU server

OLLAMA_BASE_URL = "http://127.0.0.1:11434"

OLLAMA_MODEL = "llama3"
NUM_QUESTIONS = 7

# Uncomment this to use edge TTS for TTS
'''TTS_VOICE = "en-US-GuyNeural"
TTS_RATE  = "+0%"
TTS_PITCH = "+0Hz"
'''