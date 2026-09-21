"""Grounded skill-gap analysis: matching/missing skills, aggregated gaps,
a prerequisite-based learning path, a focus track, and a skill graph.

Operates only on data already in the session (preprocessed resume +
enriched recommendations) — no resume reprocessing happens here.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from app.features.job_recommendation.skill_overlap import (
    KNOWN_SKILLS,
    extract_job_skills,
    extract_resume_skills,
)

# Category groupings used to derive the "focus track"
SKILL_CATEGORIES: Dict[str, set] = {
    "Languages & Fundamentals": {
        "Python", "Java", "C", "C++", "C#", "Go", "Rust", "R", "JavaScript",
        "TypeScript", "Kotlin", "Swift", "PHP", "Ruby", "Scala", "Perl", "MATLAB",
        "Dart", "Objective-C", "Bash", "Shell Scripting", "PowerShell", "VBA",
        "Assembly", "Haskell", "Julia", "Lua", "SQL", "Git",
    },
    "Frontend": {
        "HTML", "CSS", "React", "Angular", "Vue", "Next.js", "Svelte", "jQuery",
        "Bootstrap", "Tailwind CSS", "SASS", "Webpack", "Redux", "WebSockets",
        "Progressive Web Apps", "Web Accessibility",
    },
    "Backend / API": {
        "Node.js", "Django", "Flask", "FastAPI", "Spring Boot", "Express", "ASP.NET",
        "Ruby on Rails", "Laravel", "REST API", "GraphQL", "gRPC", "Microservices",
        "Serverless", "API Gateway", "API",
    },
    "Mobile Development": {
        "Android", "iOS", "React Native", "Flutter", "SwiftUI", "Xamarin",
        "Jetpack Compose",
    },
    "Data & Databases": {
        "NoSQL", "MongoDB", "PostgreSQL", "MySQL", "SQLite", "Redis", "Cassandra",
        "DynamoDB", "Elasticsearch", "Neo4j", "Oracle DB", "Firebase", "Data Modeling",
        "Data Warehousing", "ETL", "Snowflake", "BigQuery", "Spark", "Hadoop",
        "Kafka", "Airflow", "dbt", "Hive", "Flink", "Presto", "Pandas", "NumPy",
        "Statistics", "Data Visualization",
    },
    "ML / AI": {
        "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
        "Scikit-learn", "NLP", "Computer Vision", "LLM", "Generative AI",
        "Reinforcement Learning", "A/B Testing", "MLOps", "Feature Engineering",
        "XGBoost", "OpenCV", "Hugging Face", "LangChain", "RAG", "Prompt Engineering",
    },
    "Cloud & DevOps": {
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible",
        "Jenkins", "CI/CD", "GitHub Actions", "GitLab CI", "Linux", "Nginx", "Helm",
        "Prometheus", "Grafana", "Datadog", "Chef", "Puppet",
        "Site Reliability Engineering", "Load Balancing",
    },
    "Security": {
        "Cybersecurity", "Penetration Testing", "Ethical Hacking", "Network Security",
        "Cryptography", "OWASP", "SIEM", "Vulnerability Assessment",
        "Incident Response", "Container Security", "Identity and Access Management",
        "Firewall Configuration", "Security Auditing", "Malware Analysis",
    },
    "Testing & QA": {
        "Selenium", "Cypress", "Postman", "REST Assured", "JMeter", "JUnit", "PyTest",
        "TestNG", "Manual Testing", "Automation Testing", "Load Testing",
        "Unit Testing", "Integration Testing",
    },
    "Embedded, Hardware & Robotics": {
        "Embedded Systems", "IoT", "Arduino", "Raspberry Pi", "VHDL", "Verilog",
        "FPGA", "PCB Design", "RTOS", "ARM", "Microcontrollers", "ROS", "Robotics",
        "PLC Programming", "SCADA", "Circuit Design",
    },
    "Mechanical, Civil & Electrical Engineering": {
        "AutoCAD", "SolidWorks", "ANSYS", "Simulink", "Thermodynamics",
        "Fluid Mechanics", "Manufacturing Processes", "Six Sigma",
        "Lean Manufacturing", "Quality Control", "Supply Chain Management",
        "Structural Analysis", "CAD", "CAM", "GD&T", "Power Systems",
        "Control Systems", "Signal Processing", "VLSI Design",
    },
    "Chemical & Biotech": {
        "Chemical Process Design", "Biotechnology", "Genomics", "Bioinformatics",
        "Lab Techniques", "Quality Assurance",
    },
    "Game Development": {
        "Unity", "Unreal Engine", "Photon", "Game Design", "3D Modeling", "Blender",
    },
    "Blockchain & Web3": {
        "Blockchain", "Solidity", "Smart Contracts", "Web3", "Ethereum",
        "Cryptocurrency",
    },
    "Tools & Collaboration": {
        "GitHub", "GitLab", "Bitbucket", "JIRA", "Confluence", "Slack", "Trello",
        "Notion", "Agile", "Scrum", "Kanban", "Waterfall",
    },
    "Design & UX": {
        "UI/UX Design", "Figma", "Adobe XD", "Sketch", "Wireframing", "Prototyping",
        "User Research", "Photoshop", "Illustrator", "InDesign", "Graphic Design",
        "Canva", "Typography", "Premiere Pro", "After Effects", "Video Editing",
        "3D Animation",
    },
    "Product & Business Strategy": {
        "Product Management", "Business Analysis", "Requirement Gathering",
        "Market Research", "Competitive Analysis", "Stakeholder Management",
        "Roadmapping", "Go-to-Market Strategy", "SWOT Analysis", "KPI Tracking",
    },
    "Project Management": {
        "Project Management", "Risk Management", "Budgeting", "Resource Planning",
        "PMP", "PRINCE2", "Gantt Charts", "MS Project",
    },
    "Marketing": {
        "Digital Marketing", "SEO", "SEM", "Content Marketing",
        "Social Media Marketing", "Email Marketing", "Google Analytics",
        "Google Ads", "Copywriting", "Brand Management", "Marketing Strategy",
        "Influencer Marketing",
    },
    "Sales & CRM": {
        "Sales", "Salesforce", "HubSpot", "Lead Generation", "Negotiation",
        "Client Relationship Management", "Cold Calling", "Account Management",
    },
    "Finance & Accounting": {
        "Financial Analysis", "Accounting", "Bookkeeping", "Financial Modeling",
        "Excel", "Word", "PowerPoint", "Google Sheets", "Tally", "QuickBooks",
        "Taxation", "Auditing", "Investment Analysis", "Risk Assessment",
        "Financial Reporting", "SAP", "Equity Research", "Valuation",
    },
    "Human Resources": {
        "Human Resources", "Recruitment", "Talent Acquisition", "Payroll Management",
        "Employee Onboarding", "Performance Management", "HRIS",
        "Training and Development",
    },
    "Legal": {
        "Legal Research", "Contract Drafting", "Compliance", "Intellectual Property",
        "Corporate Law", "Litigation", "Legal Writing",
    },
    "Healthcare": {
        "Patient Care", "Clinical Research", "Medical Coding", "Nursing",
        "Pharmacology", "Healthcare Administration", "HIPAA Compliance",
        "Electronic Health Records",
    },
    "Education & Training": {
        "Curriculum Development", "Lesson Planning", "Classroom Management",
        "Instructional Design", "Tutoring", "E-Learning",
    },
    "Content & Writing": {
        "Content Writing", "Technical Writing", "Editing", "Proofreading",
        "Journalism", "Blogging", "Scriptwriting",
    },
    "Soft Skills": {
        "Communication", "Leadership", "Teamwork", "Problem Solving",
        "Critical Thinking", "Time Management", "Adaptability", "Creativity",
        "Emotional Intelligence", "Conflict Resolution", "Presentation Skills",
        "Public Speaking", "Decision Making", "Collaboration", "Work Ethic",
        "Attention to Detail", "Analytical Thinking", "Interpersonal Skills",
        "Mentoring", "Networking",
    },
}

_CATEGORY_LOOKUP: Dict[str, str] = {
    skill: category for category, skills in SKILL_CATEGORIES.items() for skill in skills
}

# missing_skill -> stepping-stone skills, in rough learning order
PREREQUISITE_MAP: Dict[str, List[str]] = {
    "Kubernetes": ["Docker", "Linux", "CI/CD"],
    "Docker": ["Linux"],
    "Helm": ["Kubernetes"],
    "Prometheus": ["Linux"],
    "Grafana": ["Prometheus"],
    "Terraform": ["AWS", "Linux"],
    "Ansible": ["Linux"],
    "AWS": ["Linux"],
    "Azure": ["Linux"],
    "GCP": ["Linux"],
    "CI/CD": ["Git"],
    "GitHub Actions": ["Git", "CI/CD"],
    "Jenkins": ["Git", "CI/CD"],
    "TensorFlow": ["Python", "Machine Learning"],
    "PyTorch": ["Python", "Machine Learning"],
    "Deep Learning": ["Machine Learning", "Python"],
    "Machine Learning": ["Python", "Pandas", "NumPy"],
    "NLP": ["Machine Learning", "Python"],
    "Computer Vision": ["Machine Learning", "Python"],
    "LLM": ["NLP", "Python"],
    "Scikit-learn": ["Python", "Pandas"],
    "Spark": ["Python", "SQL"],
    "Airflow": ["Python", "SQL"],
    "Kafka": ["Linux"],
    "dbt": ["SQL"],
    "React": ["JavaScript", "HTML", "CSS"],
    "Next.js": ["React", "JavaScript"],
    "Angular": ["JavaScript", "TypeScript"],
    "Vue": ["JavaScript"],
    "TypeScript": ["JavaScript"],
    "GraphQL": ["REST API"],
    "FastAPI": ["Python"],
    "Django": ["Python"],
    "Flask": ["Python"],
    "Spring Boot": ["Java"],
    "MongoDB": ["NoSQL"],
    "Redis": ["NoSQL"],
    "Penetration Testing": ["Network Security", "Linux"],
    "Ethical Hacking": ["Network Security", "Linux"],
    "Cybersecurity": ["Network Security", "Linux"],
    "React Native": ["React", "JavaScript"],
    "Flutter": ["Dart"],
    "Android": ["Java", "Kotlin"],
    "iOS": ["Swift"],
    "Jetpack Compose": ["Android", "Kotlin"],
    "Data Visualization": ["Pandas", "Statistics"],
    "MLOps": ["Machine Learning", "Docker", "CI/CD"],
    "Generative AI": ["Machine Learning", "Python"],
    "RAG": ["LLM", "NLP"],
    "LangChain": ["LLM", "Python"],
    "Prompt Engineering": ["LLM"],
    "Smart Contracts": ["Solidity"],
    "Web3": ["Blockchain", "JavaScript"],
    "Financial Modeling": ["Excel", "Accounting"],
    "Financial Analysis": ["Excel", "Accounting"],
    "Product Management": ["Business Analysis"],
    "Business Analysis": ["Market Research"],
    "Digital Marketing": ["SEO", "Content Marketing"],
    "Social Media Marketing": ["Digital Marketing"],
    "SIEM": ["Network Security"],
    "Vulnerability Assessment": ["Network Security"],
}

_KNOWN_SKILL_SET = set(KNOWN_SKILLS)


def _clean_resume_skills(preprocessed: dict) -> set:
    """Whitelist-only view of resume skills for this analysis: keeps only
    tokens that matched a recognized skill (via KNOWN_SKILLS/SKILL_ALIASES),
    dropping generic-word fallbacks the resume parser's NER step tags as
    'skills' (e.g. 'Backend', 'Storage', 'Dashboards'). Scoped to this
    module only — extract_resume_skills() itself is left untouched so
    tailoring and other consumers keep their existing behavior."""
    return {s for s in extract_resume_skills(preprocessed) if s in _KNOWN_SKILL_SET}

def _skill_category(skill: str) -> str:
    return _CATEGORY_LOOKUP.get(skill, "Other")


def analyze_recommendations(
    preprocessed: dict,
    recommendations: List[dict],
    top_n_jobs: int = 5,
    max_missing_per_job: int = 4,
) -> dict:
    """Reuses the already-extracted resume skills and existing recommendation
    list (does not reprocess the resume or re-run the matcher)."""
    resume_skills = _clean_resume_skills(preprocessed)
    top_jobs = sorted(recommendations, key=lambda r: r.get("rank", 999))[:top_n_jobs]

    job_breakdown: List[dict] = []
    missing_counter: Counter = Counter()
    role_demand: Dict[str, List[str]] = defaultdict(list)

    for rec in top_jobs:
        job_skills = rec.get("job_skills") or extract_job_skills(rec)
        matching = [s for s in job_skills if s in resume_skills]
        missing_all = [s for s in job_skills if s not in resume_skills]
        missing_trimmed = missing_all[:max_missing_per_job]
        title = rec.get("title") or "Untitled role"

        for skill in missing_trimmed:
            missing_counter[skill] += 1
            role_demand[skill].append(title)

        job_breakdown.append({
            "job_index": rec.get("job_index"),
            "title": title,
            "company": rec.get("company", ""),
            "matching_skills": matching,
            "missing_skills": missing_trimmed,
            "match_ratio": round(len(matching) / len(job_skills), 2) if job_skills else 0.0,
        })

    repeated_gaps = [
        {"skill": skill, "blocks_roles": count, "roles": role_demand[skill]}
        for skill, count in missing_counter.most_common()
    ]

    # Learning path: order missing skills by how many roles they block,
    # and check whether the resume already has a natural stepping stone.
    learning_path = []
    for skill, count in missing_counter.most_common():
        prereqs = PREREQUISITE_MAP.get(skill, [])
        have = [p for p in prereqs if p in resume_skills]
        need = [p for p in prereqs if p not in resume_skills and p not in missing_counter]
        if have:
            readiness = "ready_now"
            note = f"You already know {', '.join(have)} — a natural lead-in to {skill}."
        elif need:
            readiness = "needs_foundation"
            note = f"Build {', '.join(need)} first, then move to {skill}."
        else:
            readiness = "start_fresh"
            note = f"No direct prerequisite found in your resume — start {skill} from fundamentals."
        learning_path.append({
            "skill": skill,
            "category": _skill_category(skill),
            "blocks_roles": count,
            "prerequisite_skills": prereqs,
            "readiness": readiness,
            "note": note,
        })

    # Focus track: category with the highest weighted gap score
    category_scores: Counter = Counter()
    for skill, count in missing_counter.items():
        category_scores[_skill_category(skill)] += count
    focus_track = None
    if category_scores:
        name, score = category_scores.most_common(1)[0]
        focus_track = {
            "category": name,
            "score": score,
            "reason": f"{score} of your top {len(top_jobs)} recommended roles need skills in {name}.",
        }

    closest_roles = sorted(
        job_breakdown, key=lambda j: (-j["match_ratio"], len(j["missing_skills"]))
    )[:3]

    # Skill graph: current-skill nodes, missing-skill nodes, role nodes.
    # demand edges: missing skill -> role that needs it
    # prerequisite/path edges: current skill -> missing skill it leads into
    nodes: List[dict] = []
    edges: List[dict] = []
    seen_nodes: set = set()

    def _add_node(node_id: str, label: str, node_type: str) -> None:
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            nodes.append({"id": node_id, "label": label, "type": node_type})

    for skill in resume_skills:
        _add_node(f"skill::{skill}", skill, "current_skill")

    for job in job_breakdown:
        role_id = f"role::{job['job_index']}"
        _add_node(role_id, job["title"], "role")
        for skill in job["missing_skills"]:
            skill_id = f"skill::{skill}"
            _add_node(skill_id, skill, "missing_skill")
            edges.append({"source": skill_id, "target": role_id, "relation": "demanded_by"})

    for step in learning_path:
        target_id = f"skill::{step['skill']}"
        for prereq in step["prerequisite_skills"]:
            if prereq in resume_skills:
                source_id = f"skill::{prereq}"
                _add_node(source_id, prereq, "current_skill")
                edges.append({"source": source_id, "target": target_id, "relation": "leads_to"})

    return {
        "resume_skills": sorted(resume_skills),
        "jobs_analyzed": len(job_breakdown),
        "job_breakdown": job_breakdown,
        "repeated_gaps": repeated_gaps,
        "learning_path": learning_path,
        "focus_track": focus_track,
        "closest_roles": closest_roles,
        "skill_graph": {"nodes": nodes, "edges": edges},
    }