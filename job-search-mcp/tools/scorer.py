# tools/scorer.py
import json
import re

from google import genai
from config import GEMINI_API_KEY, RESUME_TEXT
from prompt import ANALYSE_JOB_PROMPT, SEARCH_QUERY_EXPANSION_PROMPT
from tools.resume_parser import extract_resume_profile

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def _parse_json_response(text: str) -> dict:
    clean = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger_fallback = {"score": 0, "recommendation": "skip", "parse_error": True, "raw_text": clean[:300]}
        return logger_fallback


def _extract_required_experience_years(job_description: str) -> int:
    text = (job_description or "").lower()

    patterns = [
        r"(?:minimum|at least|requires?\s+at least|preferably)\s+(\d+)\+?\s*years?",
        r"(\d+)\s*[-–]\s*(\d+)\s*years?",
        r"(\d+)\+?\s*years?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if len(match.groups()) == 2:
            return int(match.group(2))
        return int(match.group(1))

    return 0


def _should_skip_for_experience(resume_years: int, job_description: str) -> tuple[bool, str]:
    required_years = _extract_required_experience_years(job_description)
    resume_years = int(resume_years or 0)

    if required_years and resume_years < required_years and required_years >= 6:
        reason = (
            f"Job requires at least {required_years} years of experience, "
            f"but your resume shows {resume_years} years."
        )
        return True, reason

    return False, ""

async def score_job(job_title: str, job_description: str) -> dict:
    profile = extract_resume_profile(resume_text=RESUME_TEXT)
    prompt = f"""
Score this job against the resume. Respond ONLY in JSON:
{{"score": <0-100>, "recommendation": "apply" | "skip"}}

RESUME_PROFILE:
{profile}
JOB: {job_title} - {job_description[:500]}
"""
    if client is None:
        return {"score": 0, "recommendation": "skip", "note": "Gemini API key unavailable; resume profile was used for fallback."}
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return _parse_json_response(response.text)

async def analyse_job(
    job_title: str,
    company: str,
    job_description: str
) -> dict:
    profile = extract_resume_profile(resume_text=RESUME_TEXT)
    resume_years = int(profile.get("experience_years") or 0)
    required_years = _extract_required_experience_years(job_description)
    should_skip, skip_reason = _should_skip_for_experience(resume_years, job_description)

    if should_skip:
        return {
            "ats_score": 0,
            "match_reasons": [],
            "gaps": [skip_reason],
            "gap_severity": "high",
            "recommendation": "skip",
            "recommendation_reason": skip_reason,
            "key_skills_matched": profile.get("skills", [])[:5],
            "key_skills_missing": [],
            "email_subject": "",
            "email_draft": "",
            "interview_talking_points": [],
            "required_experience_years": required_years,
            "resume_experience_years": resume_years,
            "yoe_mismatch": True,
        }

    prompt = ANALYSE_JOB_PROMPT.format(
        resume=profile["raw_text"] or RESUME_TEXT,
        job_title=job_title,
        company=company,
        job_description=job_description[:1500]
    )
    if client is None:
        return {
            "ats_score": 0,
            "match_reasons": [],
            "gaps": ["Gemini API key unavailable"],
            "gap_severity": "high",
            "recommendation": "skip",
            "recommendation_reason": "Gemini scoring is unavailable in this environment.",
            "key_skills_matched": profile.get("skills", [])[:5],
            "key_skills_missing": [],
            "email_subject": "",
            "email_draft": "",
            "interview_talking_points": [],
            "required_experience_years": required_years,
            "resume_experience_years": resume_years,
            "yoe_mismatch": False,
        }
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    parsed = _parse_json_response(response.text)
    parsed.setdefault("required_experience_years", required_years)
    parsed.setdefault("resume_experience_years", resume_years)
    parsed.setdefault("yoe_mismatch", False)
    return parsed

async def expand_search_query(query: str) -> list[str]:
    profile = extract_resume_profile(resume_text=RESUME_TEXT)
    prompt = SEARCH_QUERY_EXPANSION_PROMPT.format(
        resume=profile["raw_text"] or RESUME_TEXT,
        query=query
    )
    if client is None:
        return [query]
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    result = _parse_json_response(response.text)
    return result.get("queries", [query])

async def prefilter_jobs(jobs: list[dict], top_n: int = 3) -> list[dict]:
    MUST_HAVE = [
        "python", "backend", "fastapi", "gcp", "ai",
        "ml", "cloud", "distributed", "api", "engineer"
    ]
    SKIP_KEYWORDS = [
        "java", "spring boot", ".net", "c#", "ruby",
        "tcs", "infosys", "wipro", "cognizant", "accenture",
        "react", "angular", "frontend", "ios", "android"
    ]
    
    scored = []
    for job in jobs:
        text = (
            (job.get("title") or "") + " " +
            (job.get("description") or "") +
            (job.get("company") or "")
        ).lower()
        
        if any(kw in text for kw in SKIP_KEYWORDS):
            continue
        
        hits = sum(1 for kw in MUST_HAVE if kw in text)
        scored.append((hits, job))
    
    scored.sort(reverse=True, key=lambda x: x[0])
    return [job for _, job in scored[:top_n]]