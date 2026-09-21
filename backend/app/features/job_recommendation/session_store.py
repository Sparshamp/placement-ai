import uuid

_sessions: dict[str, dict] = {}


def create_session(payload: dict) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = payload
    return session_id


def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        raise KeyError("Session not found")
    return _sessions[session_id]


def delete_session(session_id: str):
    _sessions.pop(session_id, None)
