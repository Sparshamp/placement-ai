# app/features/interview_simulation/session_store.py
import uuid

_sessions: dict[str, dict] = {}

def create_session(resume_text, job_description, domain) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "context": {"resume": resume_text, "job_description": job_description, "domain": domain},
        "all_qa": [],
        "all_emotions": [],
        "current_question_emotions": [],   # NEW — frames collected during the current answer
        "q_num": 1,
        "current_question": None,
        "awaiting_followup": False,   # NEW
    }
    return session_id

def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        raise KeyError("Session not found")
    return _sessions[session_id]

def delete_session(session_id: str):
    _sessions.pop(session_id, None)