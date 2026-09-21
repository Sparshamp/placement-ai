# app/features/interview_simulation/emotion_analyzer.py
import numpy as np
import cv2
from deepface import DeepFace

def analyze_frame(image_bytes: bytes) -> dict:
    """Run emotion detection on a single JPEG frame. Never raises — returns Neutral on failure."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"dominant": "Neutral", "scores": {}}

    try:
        result = DeepFace.analyze(img, actions=["emotion"], enforce_detection=False)
        if isinstance(result, list):
            result = result[0]
        return {
            "dominant": result["dominant_emotion"].capitalize(),
            "scores": {k.capitalize(): round(v, 2) for k, v in result["emotion"].items()},
        }
    except Exception:
        # no face detected, bad frame, etc. — don't crash the interview over one frame
        return {"dominant": "Neutral", "scores": {}}