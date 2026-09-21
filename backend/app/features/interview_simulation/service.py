# app/features/interview_simulation/service.py
from .resume_reader import extract_resume_text
from .stt import transcribe_uploaded_audio
from .llm import generate_question, generate_feedback, generate_final_report
#from .tts import synthesize as tts_synthesize
from .config import NUM_QUESTIONS
from . import session_store, emotion_analyzer

async def start_session(resume_file, job_description: str, domain: str):
    raw = await resume_file.read()
    resume_text = extract_resume_text(raw, resume_file.filename)

    session_id = session_store.create_session(resume_text, job_description, domain)
    session = session_store.get_session(session_id)

    intro = (
        f"Welcome to your mock interview for {domain}. "
        f"I will ask you {NUM_QUESTIONS} questions one by one. Let's begin."
    )

    question = generate_question(1, [], context=session["context"])
    session["current_question"] = question

    return {
        "sessionId": session_id,
        "intro": intro,
        "question": question,
        "questionNum": 1,
        "totalQuestions": NUM_QUESTIONS,
    }

async def record_emotion_frame(session_id: str, frame_file):
    """Called repeatedly by the frontend while the user is answering."""
    session = session_store.get_session(session_id)
    raw = await frame_file.read()
    emotion = emotion_analyzer.analyze_frame(raw)
    session["current_question_emotions"].append(emotion)
    return {"ok": True}

def _aggregate_emotions(emotion_list: list[dict]) -> dict:
    if not emotion_list:
        return {"dominant": "Neutral", "scores": {}}

    dominants = [e["dominant"] for e in emotion_list]
    dominant = max(set(dominants), key=dominants.count)

    all_keys = {k for e in emotion_list for k in e["scores"].keys()}
    avg_scores = {
        k: round(sum(e["scores"].get(k, 0) for e in emotion_list) / len(emotion_list), 2)
        for k in all_keys
    }
    return {"dominant": dominant, "scores": avg_scores}

async def submit_answer(session_id: str, audio_file):
    session = session_store.get_session(session_id)
    raw = await audio_file.read()
    answer_text = transcribe_uploaded_audio(raw) or "[No answer detected]"

    # Real aggregation from frames collected during this answer
    emotion = _aggregate_emotions(session["current_question_emotions"])
    session["current_question_emotions"] = []   # reset for next question

    # ── Case 1: this answer is a response to a FOLLOW-UP question ──
    if session["awaiting_followup"]:
        session["all_qa"][-1]["answer"] += f" | Follow-up: {answer_text}"
        session["awaiting_followup"] = False

        done = session["q_num"] >= NUM_QUESTIONS
        next_question = None
        if not done:
            session["q_num"] += 1
            next_question = generate_question(session["q_num"], session["all_qa"], context=session["context"])
            session["current_question"] = next_question

        return {
            "feedback": "Got it, thank you.",
            "emotion": emotion,
            "nextQuestion": next_question,
            "questionNum": session["q_num"],
            "done": done,
            "isFollowup": False,
        }

    # ── Case 2: this answer is a response to the MAIN question ──
    question = session["current_question"]
    feedback = generate_feedback(question, answer_text, previous_qa=session["all_qa"], context=session["context"])

    session["all_qa"].append({"question": question, "answer": answer_text, "feedback": feedback})
    session["all_emotions"].append({"question_num": session["q_num"], **emotion})

    # If feedback ends with "?", it IS a follow-up question — matches your original logic
    if feedback.strip().endswith("?"):
        session["awaiting_followup"] = True
        session["current_question"] = feedback
        return {
            "feedback": feedback,
            "emotion": emotion,
            "nextQuestion": None,
            "questionNum": session["q_num"],
            "done": False,
            "isFollowup": True,
        }

    done = session["q_num"] >= NUM_QUESTIONS
    next_question = None
    if not done:
        session["q_num"] += 1
        next_question = generate_question(session["q_num"], session["all_qa"], context=session["context"])
        session["current_question"] = next_question

    return {
        "feedback": feedback,
        "emotion": emotion,
        "nextQuestion": next_question,
        "questionNum": session["q_num"],
        "done": done,
        "isFollowup": False,
    }

async def get_final_report(session_id: str):
    session = session_store.get_session(session_id)
    final_report = generate_final_report(session["all_qa"], context=session["context"])

    dominants = [e["dominant"] for e in session["all_emotions"]]
    overall = max(set(dominants), key=dominants.count) if dominants else "Neutral"

    return {
        "finalReport": final_report,
        "emotionSummary": {"overall_dominant": overall, "per_question": session["all_emotions"]},
    }

# Uncomment this to use edge TTS for TTS
'''async def synthesize_speech(text: str) -> bytes:
    return await tts_synthesize(text)
'''

async def close_session(session_id: str):
    session_store.delete_session(session_id)