"""Main server entry point."""

# server.py
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
import asyncio
import json
import sys

from tools.search import search_jobs
from tools.scorer import score_job
from tools.tracker import track_job
from tools.scorer import score_job, analyse_job, prefilter_jobs
from prompt import ANALYSE_JOB_PROMPT

server = FastMCP(name="job-search-agent")

@server.tool(
    name="search_jobs",
    description="Search for backend/AI engineering jobs",
)
async def search_jobs_tool(query: str, location: str = "India") -> str:
    results = await search_jobs(query, location)
    return json.dumps(results, indent=2)

@server.tool(
    name="score_job",
    description="Score a job description against resume using Gemini",
)
async def score_job_tool(job_title: str, job_description: str) -> str:
    result = await score_job(job_title, job_description)
    return json.dumps(result, indent=2)

@server.tool(
    name="track_job",
    description="Add a job to Google Sheets tracking",
)
async def track_job_tool(
    title: str,
    company: str,
    apply_link: str,
    score: int,
    recommendation: str,
) -> str:
    result = await track_job(title, company, apply_link, score, recommendation)
    return json.dumps(result, indent=2)

@server.tool(
    name="analyse_job",
    description="Deeply analyse a single job. Returns ATS score, gaps, recommendation, email draft and talking points.",
)
async def analyse_job_tool(
    job_title: str,
    company: str,
    job_description: str
) -> str:
    result = await analyse_job(job_title, company, job_description)
    return json.dumps(result, indent=2)

@server.tool(
    name="search_and_analyse",
    description="Full pipeline: search jobs, prefilter top 3, analyse each with Gemini. Returns scored results with email drafts.",
)
async def search_and_analyse_tool(
    query: str,
    location: str = "India",
    min_score: int = 70
) -> str:
    # Step 1 — fetch
    jobs = await search_jobs(query, location)
    
    # Step 2 — prefilter free
    shortlisted = await prefilter_jobs(jobs, top_n=3)
    
    if not shortlisted:
        return json.dumps({"message": "No relevant jobs found after filtering"})
    
    # Step 3 — analyse top 3
    results = []
    for job in shortlisted:
        analysis = await analyse_job(
            job["title"],
            job["company"],
            job["description"]
        )
        combined = {
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "apply_link": job["apply_link"],
            "posted": job["posted"],
            **analysis
        }
        if combined.get("ats_score", 0) >= min_score:
            results.append(combined)
    
    results.sort(key=lambda x: x.get("ats_score", 0), reverse=True)
    return json.dumps(results, indent=2)

# ── Run server ────────────────────────────────────────────
async def main():
    print("Server ready: waiting for MCP stdio requests...", file=sys.stderr)
    await server.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
