# tools/search.py
import httpx
from config import JSEARCH_API_KEY

async def search_jobs(query: str, location: str = "India") -> list[dict]:
    """Fetch jobs from JSearch API"""
    
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
    
    # Return clean structure
    return [
        {
            "title": job.get("job_title"),
            "company": job.get("employer_name"),
            "location": job.get("job_city"),
            "description": job.get("job_description", "")[:500],
            "apply_link": job.get("job_apply_link"),
            "posted": job.get("job_posted_at_datetime_utc")
        }
        for job in jobs
    ]