"""Local test harness for job-search-mcp tools."""

import argparse
import asyncio
import json

from tools.search import search_jobs
from tools.scorer import score_job
from tools.tracker import track_job


async def run_search(args):
    try:
        results = await search_jobs(args.query, args.location)
        print(json.dumps(results, indent=2))
    except Exception as exc:
        print("Error: could not fetch jobs.")
        print(str(exc))


async def run_score(args):
    result = await score_job(args.job_title, args.job_description)
    print(json.dumps(result, indent=2))


async def run_track(args):
    result = await track_job(
        title=args.title,
        company=args.company,
        apply_link=args.apply_link,
        score=args.score,
        recommendation=args.recommendation,
    )
    print(json.dumps(result, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="Local test harness for job-search-mcp tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Run the search_jobs tool")
    search_parser.add_argument("query", help="Job query")
    search_parser.add_argument("--location", default="India", help="Job location")
    search_parser.set_defaults(func=run_search)

    score_parser = subparsers.add_parser("score", help="Run the score_job tool")
    score_parser.add_argument("job_title", help="Job title")
    score_parser.add_argument("job_description", help="Job description")
    score_parser.set_defaults(func=run_score)

    track_parser = subparsers.add_parser("track", help="Run the track_job tool")
    track_parser.add_argument("title", help="Job title")
    track_parser.add_argument("company", help="Company name")
    track_parser.add_argument("apply_link", help="Application link")
    track_parser.add_argument("score", type=int, help="Score")
    track_parser.add_argument("recommendation", choices=["apply", "skip"], help="Recommendation")
    track_parser.set_defaults(func=run_track)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
