# app/features/interview_simulation/schemas.py
from typing import Optional
from pydantic import BaseModel

class StartResponse(BaseModel):
    sessionId: str
    intro: str
    question: str
    questionNum: int
    totalQuestions: int

class AnswerResponse(BaseModel):
    feedback: str
    emotion: dict
    nextQuestion: Optional[str] = None
    questionNum: int
    done: bool
    isFollowup: bool

class ReportResponse(BaseModel):
    finalReport: str
    emotionSummary: dict

# Uncomment this to use edge TTS for TTS
'''class TTSRequest(BaseModel):
    text: str'''