# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.features.interview_simulation.router import router as interview_router
from app.features.adaptive_aptitude.router import router as aptitude_router
from app.features.job_recommendation.router import router as recommendation_router
from app.shared.auth.router import router as auth_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default dev port
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview_router)
app.include_router(aptitude_router)
app.include_router(recommendation_router)
app.include_router(auth_router)