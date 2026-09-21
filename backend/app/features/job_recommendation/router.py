from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse

from . import service
from .schemas import JobDetail, RecommendResponse, SkillGapAnalysisResponse, TailoredResumeResponse

router = APIRouter(prefix="/api/job-recommendation", tags=["job-recommendation"])


@router.get("/")
def root():
    return {"status": "running", "service": "Job Recommendation"}


@router.post("/sessions", response_model=RecommendResponse)
async def start_session(
    resume: UploadFile = File(...),
    top_k: int = Query(12, ge=1, le=30),
):
    return await service.recommend_from_resume(resume, top_k=top_k)


@router.get("/sessions/{session_id}", response_model=RecommendResponse)
def get_session(session_id: str):
    return service.get_session_jobs(session_id)


@router.get("/sessions/{session_id}/jobs/{job_index}", response_model=JobDetail)
def get_job(session_id: str, job_index: int):
    return service.get_job_detail(session_id, job_index)


@router.post("/sessions/{session_id}/jobs/{job_index}/tailored-resume", response_model=TailoredResumeResponse)
def tailor_resume(session_id: str, job_index: int):
    payload = service.generate_tailored(session_id, job_index)
    payload.pop("_docx_path", None)
    return payload


@router.get("/sessions/{session_id}/jobs/{job_index}/tailored-resume.docx")
def download_tailored_resume(session_id: str, job_index: int):
    path = service.tailored_docx_path(session_id, job_index)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )

@router.get("/sessions/{session_id}/skill-gap-analysis", response_model=SkillGapAnalysisResponse)
def get_skill_gap_analysis(session_id: str, top_n: int = Query(5, ge=1, le=15)):
    return service.analyze_session_recommendations(session_id, top_n=top_n)