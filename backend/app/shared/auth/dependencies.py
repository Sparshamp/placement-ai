from fastapi import Header, HTTPException

from app.shared.security import decode_access_token


def get_current_student(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    payload = decode_access_token(authorization.removeprefix("Bearer "))
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    return {"student_id": payload["sub"], "email": payload["email"]}