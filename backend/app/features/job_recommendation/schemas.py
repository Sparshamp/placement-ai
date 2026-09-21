from typing import List, Optional

from pydantic import BaseModel, Field


class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    location: str = ""
    years_exp: str = ""
    skills: List[str] = Field(default_factory=list)


class JobCard(BaseModel):
    jobIndex: int
    rank: int
    title: str
    company: str
    location: str = ""
    workType: str = ""
    domain: str = ""
    experienceLevel: str = ""
    salary: str = ""
    skills: List[str] = Field(default_factory=list)
    matchingSkills: List[str] = Field(default_factory=list)
    summary: str = ""
    relevancePercent: Optional[int] = None


class JobDetail(JobCard):
    description: str = ""
    relevanceNote: str = ""
    relatedSkills: List[str] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    sessionId: str
    profile: ResumeProfile
    jobs: List[JobCard]


class TailoredResumeResponse(BaseModel):
    jobIndex: int
    title: str
    company: str
    resumeMarkdown: str
    summary: str
    focus: List[str] = Field(default_factory=list)
    tailoredFromOriginal: bool = True
    downloadPath: str = ""

class SkillGapJob(BaseModel):
    jobIndex: int
    title: str
    company: str = ""
    matchingSkills: List[str] = Field(default_factory=list)
    missingSkills: List[str] = Field(default_factory=list)
    matchRatio: float = 0.0


class RepeatedGap(BaseModel):
    skill: str
    blocksRoles: int
    roles: List[str] = Field(default_factory=list)


class LearningStep(BaseModel):
    skill: str
    category: str
    blocksRoles: int
    prerequisiteSkills: List[str] = Field(default_factory=list)
    readiness: str
    note: str


class FocusTrack(BaseModel):
    category: str
    score: int
    reason: str


class SkillGraphNode(BaseModel):
    id: str
    label: str
    type: str


class SkillGraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class SkillGraph(BaseModel):
    nodes: List[SkillGraphNode] = Field(default_factory=list)
    edges: List[SkillGraphEdge] = Field(default_factory=list)


class SkillGapExplanation(BaseModel):
    summary: str = ""
    jobAdvice: List[dict] = Field(default_factory=list)
    strategicLearningSequence: List[str] = Field(default_factory=list)
    usedLlm: bool = False
    backend: str = "grounded-fallback"


class SkillGapAnalysisResponse(BaseModel):
    sessionId: str
    resumeSkills: List[str] = Field(default_factory=list)
    jobsAnalyzed: int = 0
    jobBreakdown: List[SkillGapJob] = Field(default_factory=list)
    repeatedGaps: List[RepeatedGap] = Field(default_factory=list)
    learningPath: List[LearningStep] = Field(default_factory=list)
    focusTrack: Optional[FocusTrack] = None
    closestRoles: List[SkillGapJob] = Field(default_factory=list)
    skillGraph: SkillGraph
    explanation: SkillGapExplanation