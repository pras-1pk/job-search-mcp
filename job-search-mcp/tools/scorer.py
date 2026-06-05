# tools/scorer.py
from google import genai
from google.genai import types as genai_types
from config import GEMINI_API_KEY, RESUME_TEXT
from prompt import ANALYSE_JOB_PROMPT, SEARCH_QUERY_EXPANSION_PROMPT
import json

client = genai.Client(api_key=GEMINI_API_KEY)

def _parse_json_response(text: str) -> dict:
    clean = text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)

async def score_job(job_title: str, job_description: str) -> dict:
    prompt = f"""
Score this job against the resume. Respond ONLY in JSON:
{{"score": <0-100>, "recommendation": "apply" | "skip"}}

RESUME: {RESUME_TEXT}
JOB: {job_title} - {job_description[:500]}
"""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return _parse_json_response(response.text)

async def analyse_job(
    job_title: str,
    company: str,
    job_description: str
) -> dict:
    prompt = ANALYSE_JOB_PROMPT.format(
        resume=RESUME_TEXT,
        job_title=job_title,
        company=company,
        job_description=job_description[:1500]
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return _parse_json_response(response.text)

async def expand_search_query(query: str) -> list[str]:
    prompt = SEARCH_QUERY_EXPANSION_PROMPT.format(
        resume=RESUME_TEXT,
        query=query
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash",
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