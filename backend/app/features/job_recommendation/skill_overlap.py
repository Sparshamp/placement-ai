"""Skill overlap helpers adapted from the recommendation repo's skill_analysis.

Used to present matching skills to the user and to feed resume tailoring.
Does not expose model/evaluation internals.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from app.features.job_recommendation.config import DEFAULT_JOBS_CSV
SKILL_ALIASES = {
    "amazon web services": "AWS",
    "aws ecs": "AWS",
    "aws ec2": "AWS",
    "aws lambda": "AWS",
    "ci cd": "CI/CD",
    "ci/cd": "CI/CD",
    "github actions": "GitHub Actions",
    "rest apis": "REST API",
    "rest api": "REST API",
    "apis": "API",
    "machine learn": "Machine Learning",
    "deep learn": "Deep Learning",
    "scikit learn": "Scikit-learn",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "fast api": "FastAPI",
    "node.js": "Node.js",
    "node": "Node.js",
    "js": "JavaScript",
    "ts": "TypeScript",
    "c sharp": "C#",
    "c plus plus": "C++",
    "nlp": "NLP",
    "llms": "LLM",
    "llm": "LLM",
    "k8s": "Kubernetes",
    "gcp": "GCP",
    # UI/UX & design
    "ui ux": "UI/UX Design",
    "ux ui": "UI/UX Design",
    "uiux": "UI/UX Design",
    "ui/ux": "UI/UX Design",
    "user interface design": "UI/UX Design",
    "user experience design": "UI/UX Design",
    "adobe xd": "Adobe XD",
    "adobe photoshop": "Photoshop",
    "adobe illustrator": "Illustrator",
    "adobe indesign": "InDesign",
    "adobe premiere": "Premiere Pro",
    "adobe premiere pro": "Premiere Pro",
    "adobe after effects": "After Effects",
    # Office / productivity
    "ms excel": "Excel",
    "microsoft excel": "Excel",
    "excel": "Excel",
    "ms powerpoint": "PowerPoint",
    "powerpoint": "PowerPoint",
    "ms word": "Word",
    "microsoft word": "Word",
    "google sheets": "Google Sheets",
    # Soft skills
    "communication skills": "Communication",
    "verbal communication": "Communication",
    "written communication": "Communication",
    "problem-solving": "Problem Solving",
    "problem solving skills": "Problem Solving",
    "team work": "Teamwork",
    "critical thinking": "Critical Thinking",
    "time management": "Time Management",
    "public speaking": "Public Speaking",
    "interpersonal skills": "Interpersonal Skills",
    "attention to detail": "Attention to Detail",
    "decision making": "Decision Making",
    # Marketing
    "digital marketing": "Digital Marketing",
    "search engine optimization": "SEO",
    "search engine marketing": "SEM",
    "social media marketing": "Social Media Marketing",
    "content marketing": "Content Marketing",
    "google analytics": "Google Analytics",
    "google ads": "Google Ads",
    # Business / product / PM
    "project management": "Project Management",
    "product management": "Product Management",
    "business analysis": "Business Analysis",
    "requirement gathering": "Requirement Gathering",
    "stakeholder management": "Stakeholder Management",
    "go to market strategy": "Go-to-Market Strategy",
    "go-to-market": "Go-to-Market Strategy",
    "swot analysis": "SWOT Analysis",
    "pmp": "PMP",
    "prince2": "PRINCE2",
    # Finance / accounting
    "financial modeling": "Financial Modeling",
    "financial modelling": "Financial Modeling",
    "financial analysis": "Financial Analysis",
    "quickbooks": "QuickBooks",
    "tally": "Tally",
    "equity research": "Equity Research",
    # HR
    "human resources": "Human Resources",
    "talent acquisition": "Talent Acquisition",
    "hr": "Human Resources",
    "hris": "HRIS",
    "payroll": "Payroll Management",
    # Sales / CRM
    "customer relationship management": "Client Relationship Management",
    "crm": "Client Relationship Management",
    "salesforce": "Salesforce",
    "hubspot": "HubSpot",
    "lead generation": "Lead Generation",
    # Manufacturing / mechanical / civil / electrical
    "supply chain": "Supply Chain Management",
    "supply chain management": "Supply Chain Management",
    "quality control": "Quality Control",
    "quality assurance": "Quality Assurance",
    "lean manufacturing": "Lean Manufacturing",
    "six sigma": "Six Sigma",
    "auto cad": "AutoCAD",
    "autocad": "AutoCAD",
    "solid works": "SolidWorks",
    "solidworks": "SolidWorks",
    "computer aided design": "CAD",
    "cad cam": "CAM",
    "vlsi": "VLSI Design",
    # Embedded / IoT / robotics
    "internet of things": "IoT",
    "iot": "IoT",
    "embedded systems": "Embedded Systems",
    "ros": "ROS",
    "plc": "PLC Programming",
    "plc programming": "PLC Programming",
    # AI / data
    "artificial intelligence": "Machine Learning",
    "generative ai": "Generative AI",
    "gen ai": "Generative AI",
    "large language model": "LLM",
    "large language models": "LLM",
    "retrieval augmented generation": "RAG",
    "rag": "RAG",
    "prompt engineering": "Prompt Engineering",
    "computer vision": "Computer Vision",
    "natural language processing": "NLP",
    "mlops": "MLOps",
    "langchain": "LangChain",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "xgboost": "XGBoost",
    "opencv": "OpenCV",
    # Security
    "penetration testing": "Penetration Testing",
    "pentesting": "Penetration Testing",
    "ethical hacking": "Ethical Hacking",
    "network security": "Network Security",
    "cyber security": "Cybersecurity",
    "cybersecurity": "Cybersecurity",
    "vulnerability assessment": "Vulnerability Assessment",
    "incident response": "Incident Response",
    "siem": "SIEM",
    "owasp": "OWASP",
    # Blockchain
    "smart contracts": "Smart Contracts",
    "web 3": "Web3",
    "web3": "Web3",
    "cryptocurrency": "Cryptocurrency",
    # Healthcare
    "electronic health records": "Electronic Health Records",
    "ehr": "Electronic Health Records",
    "hipaa": "HIPAA Compliance",
    "medical coding": "Medical Coding",
    "clinical research": "Clinical Research",
    # Legal
    "intellectual property": "Intellectual Property",
    "contract drafting": "Contract Drafting",
    "legal research": "Legal Research",
    # Content / writing
    "content writing": "Content Writing",
    "technical writing": "Technical Writing",
    "copy writing": "Copywriting",
    "copywriting": "Copywriting",
    "script writing": "Scriptwriting",
}

KNOWN_SKILLS = [
    # Programming languages
    "Python", "Java", "C", "C++", "C#", "Go", "Rust", "R", "JavaScript", "TypeScript",
    "Kotlin", "Swift", "PHP", "Ruby", "Scala", "Perl", "MATLAB", "Dart", "Objective-C",
    "Bash", "Shell Scripting", "PowerShell", "VBA", "Assembly", "Solidity", "Haskell",
    "Julia", "Lua", "SQL",

    # Frontend / web
    "HTML", "CSS", "React", "Angular", "Vue", "Next.js", "Svelte", "jQuery", "Bootstrap",
    "Tailwind CSS", "SASS", "Webpack", "Redux", "WebSockets", "Progressive Web Apps",
    "Web Accessibility",

    # Backend / API
    "Node.js", "Django", "Flask", "FastAPI", "Spring Boot", "Express", "ASP.NET",
    "Ruby on Rails", "Laravel", "REST API", "GraphQL", "gRPC", "Microservices",
    "Serverless", "API Gateway", "API",

    # Mobile
    "Android", "iOS", "React Native", "Flutter", "SwiftUI", "Xamarin", "Jetpack Compose",

    # Databases / data engineering
    "NoSQL", "MongoDB", "PostgreSQL", "MySQL", "SQLite", "Redis", "Cassandra",
    "DynamoDB", "Elasticsearch", "Neo4j", "Oracle DB", "Firebase", "Data Modeling",
    "Data Warehousing", "ETL", "Snowflake", "BigQuery",

    # Data science / ML / AI
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
    "Scikit-learn", "NLP", "Computer Vision", "LLM", "Generative AI",
    "Reinforcement Learning", "Pandas", "NumPy", "Statistics", "Data Visualization",
    "A/B Testing", "MLOps", "Feature Engineering", "XGBoost", "OpenCV",
    "Hugging Face", "LangChain", "RAG", "Prompt Engineering",

    # Cloud & DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins",
    "CI/CD", "GitHub Actions", "GitLab CI", "Linux", "Nginx", "Helm", "Prometheus",
    "Grafana", "Datadog", "Chef", "Puppet", "Site Reliability Engineering",
    "Load Balancing",

    # Big data
    "Spark", "Hadoop", "Kafka", "Airflow", "dbt", "Hive", "Flink", "Presto",

    # Security
    "Cybersecurity", "Penetration Testing", "Ethical Hacking", "Network Security",
    "Cryptography", "OWASP", "SIEM", "Vulnerability Assessment", "Incident Response",
    "Container Security", "Identity and Access Management", "Firewall Configuration",
    "Security Auditing", "Malware Analysis",

    # Testing / QA
    "Selenium", "Cypress", "Postman", "REST Assured", "JMeter", "JUnit", "PyTest",
    "TestNG", "Manual Testing", "Automation Testing", "Load Testing", "Unit Testing",
    "Integration Testing",

    # Embedded / hardware / robotics
    "Embedded Systems", "IoT", "Arduino", "Raspberry Pi", "VHDL", "Verilog", "FPGA",
    "PCB Design", "RTOS", "ARM", "Microcontrollers", "ROS", "Robotics",
    "PLC Programming", "SCADA", "Circuit Design",

    # Mechanical / civil / electrical engineering
    "AutoCAD", "SolidWorks", "ANSYS", "Simulink", "Thermodynamics", "Fluid Mechanics",
    "Manufacturing Processes", "Six Sigma", "Lean Manufacturing", "Quality Control",
    "Supply Chain Management", "Structural Analysis", "CAD", "CAM", "GD&T",
    "Power Systems", "Control Systems", "Signal Processing", "VLSI Design",

    # Chemical / biotech
    "Chemical Process Design", "Biotechnology", "Genomics", "Bioinformatics",
    "Lab Techniques", "Quality Assurance",

    # Game dev
    "Unity", "Unreal Engine", "Photon", "Game Design", "3D Modeling", "Blender",

    # Blockchain
    "Blockchain", "Smart Contracts", "Web3", "Ethereum", "Cryptocurrency",

    # Version control & collaboration tools
    "Git", "GitHub", "GitLab", "Bitbucket", "JIRA", "Confluence", "Slack", "Trello",
    "Notion", "Agile", "Scrum", "Kanban", "Waterfall",

    # Design / UX
    "UI/UX Design", "Figma", "Adobe XD", "Sketch", "Wireframing", "Prototyping",
    "User Research", "Photoshop", "Illustrator", "InDesign", "Graphic Design",
    "Canva", "Typography", "Premiere Pro", "After Effects", "Video Editing",
    "3D Animation",

    # Product & business strategy
    "Product Management", "Business Analysis", "Requirement Gathering",
    "Market Research", "Competitive Analysis", "Stakeholder Management",
    "Roadmapping", "Go-to-Market Strategy", "SWOT Analysis", "KPI Tracking",

    # Project management
    "Project Management", "Risk Management", "Budgeting", "Resource Planning",
    "PMP", "PRINCE2", "Gantt Charts", "MS Project",

    # Marketing
    "Digital Marketing", "SEO", "SEM", "Content Marketing", "Social Media Marketing",
    "Email Marketing", "Google Analytics", "Google Ads", "Copywriting",
    "Brand Management", "Marketing Strategy", "Influencer Marketing",

    # Sales / CRM
    "Sales", "Salesforce", "HubSpot", "Lead Generation", "Negotiation",
    "Client Relationship Management", "Cold Calling", "Account Management",

    # Finance & accounting
    "Financial Analysis", "Accounting", "Bookkeeping", "Financial Modeling", "Excel",
    "Word", "PowerPoint", "Google Sheets", "Tally", "QuickBooks", "Taxation",
    "Auditing", "Investment Analysis", "Risk Assessment", "Financial Reporting",
    "SAP", "Equity Research", "Valuation",

    # HR
    "Human Resources", "Recruitment", "Talent Acquisition", "Payroll Management",
    "Employee Onboarding", "Performance Management", "HRIS",
    "Training and Development",

    # Legal
    "Legal Research", "Contract Drafting", "Compliance", "Intellectual Property",
    "Corporate Law", "Litigation", "Legal Writing",

    # Healthcare
    "Patient Care", "Clinical Research", "Medical Coding", "Nursing", "Pharmacology",
    "Healthcare Administration", "HIPAA Compliance", "Electronic Health Records",

    # Education / teaching
    "Curriculum Development", "Lesson Planning", "Classroom Management",
    "Instructional Design", "Tutoring", "E-Learning",

    # Content & writing
    "Content Writing", "Technical Writing", "Editing", "Proofreading", "Journalism",
    "Blogging", "Scriptwriting",

    # Soft skills
    "Communication", "Leadership", "Teamwork", "Problem Solving", "Critical Thinking",
    "Time Management", "Adaptability", "Creativity", "Emotional Intelligence",
    "Conflict Resolution", "Presentation Skills", "Public Speaking", "Decision Making",
    "Collaboration", "Work Ethic", "Attention to Detail", "Analytical Thinking",
    "Interpersonal Skills", "Mentoring", "Networking",
]

LOW_SIGNAL_SKILLS = {"API"}


def _clean_token(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#./-]+", " ", text.lower())).strip()


def normalize_skill(skill: str) -> str:
    raw = _clean_token(skill)
    if not raw:
        return ""
    if raw in SKILL_ALIASES:
        return SKILL_ALIASES[raw]
    for known in KNOWN_SKILLS:
        if raw == _clean_token(known):
            return known
    if len(raw) <= 2 and raw not in {"c", "r"}:
        return ""
    # Anything this long and word-heavy is a sentence fragment from NER,
    # not a real skill token (e.g. "3 years of experience building rest
    # apis using python and fastapi") — drop it rather than pass it through.
    words = raw.split()
    if len(words) > 4 or len(raw) > 40:
        return ""
    return " ".join(
        part.capitalize() if part not in {"api", "ci/cd"} else part.upper()
        for part in raw.split()
    )


@lru_cache(maxsize=1)
def load_jobs_dataframe() -> pd.DataFrame:
    path = Path(DEFAULT_JOBS_CSV)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig").fillna("")


@lru_cache(maxsize=1)
def known_skill_patterns() -> List[Tuple[str, re.Pattern]]:
    patterns = []
    for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
        token = re.escape(skill)
        patterns.append((skill, re.compile(rf"(?<![a-z0-9]){token}(?![a-z0-9])", re.IGNORECASE)))
    return patterns


def _split_skills(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[,|\n;/]+", str(text))
    return [p.strip(" -:.") for p in parts if p.strip(" -:.")]


def extract_known_skills(text: str) -> List[str]:
    if not text:
        return []
    found: List[str] = []
    seen = set()
    for skill, pattern in known_skill_patterns():
        if pattern.search(text) and skill not in seen:
            seen.add(skill)
            found.append(skill)
    return found


def canonicalize_skills(skills: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for skill in skills:
        normalized = normalize_skill(skill)
        if not normalized or len(normalized) == 1 or normalized in LOW_SIGNAL_SKILLS:
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def extract_resume_skills(preprocessed: dict) -> List[str]:
    entities = preprocessed.get("entities", {})
    sections = preprocessed.get("sections", {})
    combined = []
    combined.extend(entities.get("skills") or [])
    for section_name in ("skills", "experience", "projects", "certifications", "summary"):
        combined.extend(_split_skills(sections.get(section_name, "")))
        combined.extend(extract_known_skills(sections.get(section_name, "")))
    return canonicalize_skills(combined)


def job_row_from_rec(rec: dict) -> dict:
    jobs_df = load_jobs_dataframe()
    idx = rec.get("job_index", -1)
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        idx = -1
    if 0 <= idx < len(jobs_df):
        return jobs_df.iloc[idx].to_dict()
    return {}


def extract_job_skills(rec: dict) -> List[str]:
    row = job_row_from_rec(rec)
    combined = []
    combined.extend(_split_skills(rec.get("skills", "")))
    combined.extend(extract_known_skills(rec.get("description", "")))
    combined.extend(extract_known_skills(rec.get("title", "")))
    normalized = canonicalize_skills(combined)
    if len(normalized) >= 3:
        return normalized
    fallback = list(combined)
    fallback.extend(_split_skills(row.get("Skills", "")))
    fallback.extend(extract_known_skills(row.get("Job Description", "")))
    return canonicalize_skills(fallback)


def enrich_recommendations(preprocessed: dict, recommendations: List[dict]) -> List[Dict]:
    resume_skills = set(extract_resume_skills(preprocessed))
    enriched = []
    for rec in recommendations:
        job_skills = extract_job_skills(rec)
        overlap = [skill for skill in job_skills if skill in resume_skills]
        missing = [skill for skill in job_skills if skill not in resume_skills]
        why_parts = []
        if overlap:
            why_parts.append(
                "Your resume already includes " + ", ".join(overlap[:6]) + "."
            )
        level = rec.get("experience_level") or ""
        if level and level not in ("Not Specified", "Not Disclosed", ""):
            why_parts.append(f"This role is listed as {level}.")
        domain = rec.get("domain") or ""
        if domain:
            why_parts.append(f"It sits in the {domain} area.")
        enriched.append({
            **rec,
            "job_skills": job_skills,
            "matching_skills": overlap[:8],
            "related_skills": missing[:6],
            "relevance_note": " ".join(why_parts) if why_parts else (
                "This role is a close match to the overall content of your resume."
            ),
        })
    return enriched
