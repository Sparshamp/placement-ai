"""Extract structured entities from resume text (spaCy + skillNer + regex)."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_nlp = None
_skill_extractor = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        logger.info("Loading spaCy model (en_core_web_lg)")
        try:
            _nlp = spacy.load("en_core_web_lg")
        except OSError as exc:
            raise RuntimeError(
                "The resume analyzer needs the spaCy model en_core_web_lg. "
                "Run: python -m spacy download en_core_web_lg"
            ) from exc
    return _nlp


def _get_skill_extractor():
    global _skill_extractor
    if _skill_extractor is None:
        from spacy.matcher import PhraseMatcher
        from skillNer.general_params import SKILL_DB
        from skillNer.skill_extractor_class import SkillExtractor

        logger.info("Loading skillNer")
        nlp = _get_nlp()
        _skill_extractor = SkillExtractor(nlp, SKILL_DB, PhraseMatcher)
    return _skill_extractor


def extract_email(text: str) -> str:
    m = re.search(r"[\w\.\+\-]+@[\w\.\-]+\.\w{2,}", text)
    return m.group(0) if m else ""


def extract_phone(text: str) -> str:
    m = re.search(
        r"(\+?\d{1,3}[\s\-\.]?)?(\(?\d{3}\)?[\s\-\.]?)?\d{3}[\s\-\.]?\d{4}", text
    )
    return m.group(0).strip() if m else ""


def extract_years_experience(text: str) -> str:
    patterns = [
        r"(\d+)\+?\s*years?\s+of\s+experience",
        r"(\d+)\+?\s*yrs?\s+of\s+experience",
        r"experience\s+of\s+(\d+)\+?\s*years?",
        r"over\s+(\d+)\s+years?",
        r"(\d+)\+?\s*years?\s+experience",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1) + " years"
    return ""


def extract_spacy_entities(text: str) -> dict:
    nlp = _get_nlp()
    doc = nlp(text[:5000])

    result = {
        "name": "",
        "location": "",
        "organizations": [],
        "dates": [],
    }

    for ent in doc.ents:
        if ent.label_ == "PERSON" and not result["name"]:
            result["name"] = ent.text.strip()
        elif ent.label_ in ("GPE", "LOC") and not result["location"]:
            result["location"] = ent.text.strip()
        elif ent.label_ == "ORG":
            if ent.text.strip() not in result["organizations"]:
                result["organizations"].append(ent.text.strip())
        elif ent.label_ == "DATE":
            result["dates"].append(ent.text.strip())

    return result


def extract_skills(text: str) -> list:
    if not text.strip():
        return []

    extractor = _get_skill_extractor()
    try:
        annotations = extractor.annotate(text)
        skills = []

        for match in annotations.get("results", {}).get("full_matches", []):
            skills.append(match["doc_node_value"])

        for match in annotations.get("results", {}).get("ngram_scored", []):
            if match.get("score", 0) >= 0.8:
                skills.append(match["doc_node_value"])

        seen, unique = set(), []
        for s in skills:
            key = s.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique
    except Exception as e:
        logger.warning("skillNer error: %s", e)
        return []


def extract_all_entities(raw_text: str, sections: dict) -> dict:
    email = extract_email(raw_text)
    phone = extract_phone(raw_text)
    years = extract_years_experience(
        sections.get("summary", "") + " " + sections.get("experience", "")
    )
    spacy_ents = extract_spacy_entities(raw_text)
    skill_text = " ".join([
        sections.get("skills", ""),
        sections.get("experience", ""),
        sections.get("projects", ""),
    ])
    skills = extract_skills(skill_text)

    return {
        "name": spacy_ents["name"],
        "email": email,
        "phone": phone,
        "location": spacy_ents["location"],
        "skills": skills,
        "organizations": spacy_ents["organizations"],
        "dates": spacy_ents["dates"],
        "years_exp": years,
    }
