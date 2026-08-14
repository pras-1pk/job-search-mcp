# tools/search.py
import httpx
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from config import JSEARCH_API_KEY

GREENHOUSE_COMPANIES = {
    "postman": "postman",
    "cloudflare": "cloudflare",
    "stripe": "stripe",
    "flipkart": "flipkart",
    "adobe": "adobe",
}

LEVER_COMPANIES = {
    "razorpay": "razorpay",
    "phonepe": "phonepe",
    "meesho": "meesho",
    "groww": "groww",
}

ATS_COMPANIES = {**GREENHOUSE_COMPANIES, **LEVER_COMPANIES}


def _greenhouse_apply_url(company: str, item: dict) -> str | None:
    """Return the reliable Greenhouse job-board URL for a role entry."""
    slug = ATS_COMPANIES.get((company or "").lower().strip())
    if not slug:
        return item.get("absolute_url") or item.get("url")

    job_id = item.get("id") or item.get("job_id") or item.get("gh_id")
    if job_id:
        return f"https://job-boards.greenhouse.io/{slug}/jobs/{job_id}"

    absolute_url = item.get("absolute_url") or item.get("url")
    if absolute_url and "job-boards.greenhouse.io" in absolute_url:
        return absolute_url
    return absolute_url


def _detect_ats_company(query: str) -> str | None:
    normalized = (query or "").lower()
    for company in ATS_COMPANIES:
        if company in normalized:
            return company
    return None


async def fetch_ats_jobs(company: str, location: str = "India") -> list[dict]:
    """Fetch live jobs from Greenhouse or Lever for the whitelisted company set."""
    slug = ATS_COMPANIES.get((company or "").lower().strip())
    if not slug:
        return []

    try:
        if company.lower() in GREENHOUSE_COMPANIES:
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
            payload = response.json() or {}
            jobs = []
            for item in payload.get("jobs", []) or []:
                job_location = item.get("location") or ""
                if location and location.lower() not in job_location.lower() and "india" not in job_location.lower():
                    continue
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name") or company.title(),
                    "location": job_location,
                    "description": (item.get("content") or "")[:500],
                    "apply_link": _greenhouse_apply_url(company, item),
                    "posted": item.get("updated_at") or item.get("created_at"),
                })
            return jobs

        if company.lower() in LEVER_COMPANIES:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
            payload = response.json() or []
            jobs = []
            for item in payload:
                categories = item.get("categories", {}) or {}
                job_location = categories.get("location") or item.get("location") or ""
                if location and location.lower() not in job_location.lower() and "india" not in job_location.lower():
                    continue
                jobs.append({
                    "title": (item.get("text") or {}).get("title") or item.get("title"),
                    "company": (item.get("org") or {}).get("name") or company.title(),
                    "location": job_location,
                    "description": (item.get("description") or "")[:500],
                    "apply_link": item.get("hostedUrl") or item.get("applyUrl") or item.get("url"),
                    "posted": item.get("createdAt") or item.get("updatedAt"),
                })
            return jobs
    except Exception:
        return []

    return []


async def is_link_alive(url: str) -> bool:
    """Check whether an apply link is still live using HEAD and a GET fallback."""
    if not url:
        return False
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.head(url, headers={"User-Agent": "job-search-mcp/1.0"})
            if response.status_code in {200, 201, 202, 204}:
                return True
            if response.status_code in {301, 302, 307, 308}:
                location = response.headers.get("location")
                if location:
                    return await is_link_alive(urljoin(url, location))
            if response.status_code in {405, 403, 500}:
                fallback = await client.get(url, headers={"User-Agent": "job-search-mcp/1.0"})
                return fallback.is_success
            return response.is_success
    except Exception:
        return False


def is_fresh(posted_str: str, max_days: int = 14) -> bool:
    """Return True when the job was posted within the freshness window."""
    try:
        posted = datetime.fromisoformat((posted_str or "").replace("Z", "+00:00"))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - posted) <= timedelta(days=max_days)
    except Exception:
        return False


async def search_jobs(query: str, location: str = "India") -> list[dict]:
    """Fetch jobs from ATS for whitelisted companies, otherwise fall back to JSearch."""

    ats_company = _detect_ats_company(query)
    if ats_company:
        jobs = await fetch_ats_jobs(ats_company, location)
        filtered_jobs = []
        for job in jobs:
            apply_link = job.get("apply_link")
            posted = job.get("posted")
            if not apply_link or not await is_link_alive(apply_link):
                continue
            if not is_fresh(posted):
                continue
            filtered_jobs.append({
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "description": job.get("description", "")[:500],
                "apply_link": apply_link,
                "posted": posted,
            })
        if filtered_jobs:
            return filtered_jobs

    headers = {
        "X-RapidAPI-Key": JSEARCH_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    params = {
        "query": f"{query} in {location}",
        "num_results": "10",
        "date_posted": "week"
    }
    
    timeout = httpx.Timeout(30.0, read=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            "https://jsearch.p.rapidapi.com/search",
            headers=headers,
            params=params
        )
    
    jobs = response.json().get("data", [])

    filtered_jobs = []
    for job in jobs:
        apply_link = job.get("job_apply_link")
        posted = job.get("job_posted_at_datetime_utc")

        if not apply_link or not await is_link_alive(apply_link):
            continue
        if not is_fresh(posted):
            continue

        filtered_jobs.append({
            "title": job.get("job_title"),
            "company": job.get("employer_name"),
            "location": job.get("job_city"),
            "description": job.get("job_description", "")[:500],
            "apply_link": apply_link,
            "posted": posted,
        })

    return filtered_jobs