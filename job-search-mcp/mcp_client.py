"""MCP client helper for the job-search-mcp server."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).parent.resolve()


def format_output(value):
    try:
        return json.dumps(value, indent=2)
    except TypeError:
        return str(value)


async def run_client(commands):
    server = StdioServerParameters(
        command=sys.executable,
        args=["-u", str(ROOT / "server.py")],
        cwd=str(ROOT),
    )

    async with stdio_client(server) as (read_stream, write_stream):
        session = ClientSession(read_stream, write_stream)
        await session.initialize()

        if commands[0] == "list":
            tools = await session.list_tools()
            print(format_output(tools.model_dump(by_alias=True)))
            return

        if commands[0] == "call":
            name = commands[1]
            arguments = json.loads(commands[2]) if len(commands) > 2 else None
            result = await session.call_tool(name, arguments)
            print(format_output(result.model_dump(by_alias=True)))
            return

        if commands[0] == "search":
            result = await session.call_tool(
                "search_jobs",
                {
                    "query": commands[1],
                    "location": commands[2],
                },
            )
            print(format_output(result.model_dump(by_alias=True)))
            return

        if commands[0] == "score":
            result = await session.call_tool(
                "score_job",
                {
                    "job_title": commands[1],
                    "job_description": commands[2],
                },
            )
            print(format_output(result.model_dump(by_alias=True)))
            return

        if commands[0] == "track":
            result = await session.call_tool(
                "track_job",
                {
                    "title": commands[1],
                    "company": commands[2],
                    "apply_link": commands[3],
                    "score": int(commands[4]),
                    "recommendation": commands[5],
                },
            )
            print(format_output(result.model_dump(by_alias=True)))
            return

        raise ValueError(f"Unknown client command: {commands[0]}")


def build_parser():
    parser = argparse.ArgumentParser(description="MCP client for job-search-mcp server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available MCP tools")

    search_parser = subparsers.add_parser("search", help="Call search_jobs via MCP")
    search_parser.add_argument("query")
    search_parser.add_argument("location", nargs="?", default="India")

    score_parser = subparsers.add_parser("score", help="Call score_job via MCP")
    score_parser.add_argument("job_title")
    score_parser.add_argument("job_description")

    track_parser = subparsers.add_parser("track", help="Call track_job via MCP")
    track_parser.add_argument("title")
    track_parser.add_argument("company")
    track_parser.add_argument("apply_link")
    track_parser.add_argument("score", type=int)
    track_parser.add_argument("recommendation", choices=["apply", "skip"])

    call_parser = subparsers.add_parser("call", help="Call an arbitrary MCP tool")
    call_parser.add_argument("name")
    call_parser.add_argument("arguments", nargs="?", default="{}")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    commands = [args.command]

    if args.command == "search":
        commands += [args.query, args.location]
    elif args.command == "score":
        commands += [args.job_title, args.job_description]
    elif args.command == "track":
        commands += [args.title, args.company, args.apply_link, str(args.score), args.recommendation]
    elif args.command == "call":
        commands += [args.name, args.arguments]

    asyncio.run(run_client(commands))


if __name__ == "__main__":
    main()
