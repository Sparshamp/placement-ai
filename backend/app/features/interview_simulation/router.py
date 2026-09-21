# app/features/interview_simulation/router.py
#from fastapi import APIRouter, UploadFile, File, Form, Response
#from .schemas import StartResponse, AnswerResponse, ReportResponse, TTSRequest
from fastapi import APIRouter, UploadFile, File, Form
from .schemas import StartResponse, AnswerResponse, ReportResponse
from . import service

router = APIRouter(prefix="/api/interview-simulation", tags=["interview-simulation"])

@router.post("/sessions", response_model=StartResponse)
async def start_session(resume: UploadFile = File(...), job_description: str = Form(...), domain: str = Form(...)):
    return await service.start_session(resume, job_description, domain)

@router.post("/sessions/{session_id}/emotion-frame")
async def submit_emotion_frame(session_id: str, frame: UploadFile = File(...)):
    return await service.record_emotion_frame(session_id, frame)

@router.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(session_id: str, audio: UploadFile = File(...)):
    return await service.submit_answer(session_id, audio)

@router.get("/sessions/{session_id}/report", response_model=ReportResponse)
async def get_report(session_id: str):
    return await service.get_final_report(session_id)

# Uncomment this to use edge TTS for TTS
'''@router.post("/tts")
async def synthesize_speech(payload: TTSRequest):
    audio_bytes = await service.synthesize_speech(payload.text)
    return Response(content=audio_bytes, media_type="audio/mpeg")
'''

@router.delete("/sessions/{session_id}")
async def end_session(session_id: str):
    await service.close_session(session_id)
    return {"ok": True}