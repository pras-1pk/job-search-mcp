import asyncio
import json
import re
import logging
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from httpx import AsyncClient
from httpx_retries import RetryTransport, Retry  # type: ignore[import-not-found]
import urllib.robotparser as robotparser

from tools.search import search_jobs as search_web_jobs

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - optional dependency fallback
    async_playwright = None

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency fallback
    yaml = None

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPANIES_FILE = PROJECT_ROOT / "companies.yml"

# Use a custom user-agent
USER_AGENT = "job-search-mcp/1.0"

DEFAULT_ROLE_KEYWORDS = [
    "sde2 backend", "backend platform engineer", "distributed systems engineer",
    "cloud backend engineer", "python backend engineer"
]
AREA_KEYWORDS = [
    "distributed pipelines", "async systems", "redis", "event-driven",
    "pubsub", "gcp", "fastapi", "cloud", "machine learning", "ai"
]

LOCATION_KEYWORDS = [
    "india", "bangalore", "bengaluru", "hyderabad",
    "pune", "gurgaon", "noida", "chennai"
]

PRIORITY_WEIGHTS = {
    "high": 3,
    "medium": 2,
    "low": 1,
}

class LinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if not href:
            return
        # Resolve relative URLs
        href = urljoin(self.base_url, href)
        if href.startswith("http"):
            self.links.append((href, attrs.get("title") or ""))


async def fetch_text(client: AsyncClient, url: str) -> str:
    """Fetch page HTML with httpx and fall back to Playwright only when needed."""
    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text
    except httpx.RequestError as e:
        logger.warning(f"Request failed for {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        raise


async def fetch_text_playwright(page, url: str) -> str:
    """Fetch page HTML through an existing Playwright page, with an httpx fallback."""
    if page is None:
        raise RuntimeError("Playwright page is not available")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_load_state("networkidle", timeout=120000)
        return await page.content()
    except Exception as exc:
        logger.info("Playwright page load failed for %s: %s", url, exc)
        raise


async def is_allowed_to_crawl(base_url: str) -> bool:
    """Check robots.txt to see if crawling is permitted for our user-agent."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as e:
        logger.info(f"No robots.txt found at {robots_url}: {e}")
        return True  # Assume allowed if robots.txt is unreachable
    allowed = rp.can_fetch(USER_AGENT, base_url)
    if not allowed:
        logger.info(f"Disallowed by robots.txt: {base_url}")
    # Honor crawl delay if present
    delay = rp.crawl_delay(USER_AGENT)
    if delay:
        logger.info(f"Sleeping for crawl-delay: {delay}s")
        await asyncio.sleep(delay)
    return allowed

def score_relevance(text: str, keywords: Iterable[str]) -> int:
    """Simple relevance scoring based on keyword occurrences."""
    lowered = text.lower()
    score = 0
    for keyword in keywords:
        if keyword.lower() in lowered:
            score += 2
    return score


def _score_relevance(text: str, keywords: Iterable[str]) -> int:
    """Backward-compatible alias used by the Phase 2 tests."""
    return score_relevance(text, keywords)


def _priority_weight(target: dict) -> int:
    """Return a simple priority weight from the configured company preferences."""
    return PRIORITY_WEIGHTS.get((target.get("priority") or "").lower(), 0)


def load_company_targets(path: str | Path = DEFAULT_COMPANIES_FILE) -> list[dict]:
    """Load company targets from the YAML config file."""
    if yaml is None:
        logger.warning("PyYAML is not installed; falling back to an empty company list.")
        return []

    config_path = Path(path)
    if not config_path.exists():
        logger.warning("Company config file not found: %s", config_path)
        return []

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:
        logger.warning("Failed to read company config: %s", exc)
        return []

    companies = data.get("companies", []) if isinstance(data, dict) else []
    return [dict(item) for item in companies if isinstance(item, dict)]

async def collect_links(client: AsyncClient, base_url: str, keywords: list[str]) -> list[dict]:
    """Collect candidate links from a given URL."""
    if not await is_allowed_to_crawl(base_url):
        return []
    try:
        html = await fetch_text(client, base_url)
    except Exception:
        return []
    parser = LinkParser(base_url)
    parser.feed(html)
    results = []
    seen = set()
    for href, title in parser.links:
        if href in seen:
            continue
        seen.add(href)
        # Filter career-related links
        if any(tok in href.lower() for tok in ("career", "job", "join", "opportun", "recruit")):
            text = (title or href)
            relevance = score_relevance(text + " " + href, keywords)
            if relevance > 0:
                results.append({"title": text, "url": href, "relevance": relevance})
    return results

async def crawl_company_careers(company: str, role_keywords: list[str] | None = None, max_results: int = 5) -> list[dict]:
    """
    Crawl a company's career pages and return the top matching job links.
    If the company name is "all" or "companies", the YAML config file is used.
    """
    keywords = [(kw.strip().lower()) for kw in (role_keywords or DEFAULT_ROLE_KEYWORDS)]
    keywords = list(dict.fromkeys([
        *keywords,
        *[kw.lower() for kw in AREA_KEYWORDS],
        *[kw.lower() for kw in LOCATION_KEYWORDS],
    ]))

    company_targets = load_company_targets()
    use_config = company.lower() in {"all", "all_companies", "companies"}
    targets = company_targets if use_config and company_targets else [{"name": company, "career_url": None}]
    targets = sorted(targets, key=lambda item: _priority_weight(item), reverse=True)

    all_results = []
    playwright = None
    browser = None
    page = None

    if async_playwright is not None:
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=USER_AGENT)
        except Exception as exc:
            logger.warning("Playwright startup failed; using httpx-only path: %s", exc)
            if browser is not None:
                await browser.close()
            if playwright is not None:
                await playwright.stop()
            browser = None
            page = None

    try:
        for target in targets:
            target_name = target.get("name") or company
            career_url = target.get("career_url")
            normalized = re.sub(r"[^a-z0-9]+", "", target_name.lower())

            candidates = [
                career_url,
                f"https://{normalized}.com/careers",
                f"https://{normalized}.com/jobs",
                f"https://www.{normalized}.com/careers",
                f"https://www.{normalized}.com/jobs",
                f"https://careers.{normalized}.com/",
            ]
            candidates = [url for url in candidates if url]

            if not candidates:
                continue

            retry = Retry(total=3, backoff_factor=0.5)
            transport = RetryTransport(retry=retry)
            async with AsyncClient(transport=transport, timeout=10.0, verify=True) as client:
                collected = []
                local_seen = set()
                for url in candidates:
                    if not await is_allowed_to_crawl(url):
                        continue
                    try:
                        html = await fetch_text_playwright(page, url) if page is not None else await fetch_text(client, url)
                        parser = LinkParser(url)
                        parser.feed(html)
                        for href, title in parser.links:
                            if href in local_seen:
                                continue
                            local_seen.add(href)
                            if any(tok in href.lower() for tok in ("career", "job", "join", "opportun", "recruit")):
                                text = title or href
                                relevance = score_relevance(text + " " + href, keywords)
                                if relevance > 0:
                                    collected.append({"title": text, "url": href, "relevance": relevance})
                    except Exception as exc:
                        logger.warning("Failed to parse %s: %s", url, exc)

                if not collected:
                    try:
                        web_jobs = await search_web_jobs(f"{target_name} jobs", "India")
                        for job in web_jobs[:max_results]:
                            company_name = (job.get("company") or "").lower()
                            title = (job.get("title") or "").lower()
                            if target_name.lower() in company_name or target_name.lower() in title:
                                collected.append({
                                    "title": job.get("title") or target_name,
                                    "url": job.get("apply_link") or "",
                                    "relevance": 5 + _priority_weight(target),
                                })
                    except Exception as exc:
                        logger.warning("Web search fallback failed for %s: %s", target_name, exc)

                results = []
                for item in collected[:max_results]:
                    url = item["url"]
                    try:
                        html = await fetch_text_playwright(page, url) if page is not None else await fetch_text(client, url)
                        text = re.sub(r"<[^>]+>", " ", html)
                        norm = re.sub(r"\s+", " ", text)
                        title = norm.split("\n", 1)[0].strip()[:120]
                        relevance = max(item["relevance"], score_relevance(norm, keywords)) + _priority_weight(target)
                        results.append({
                            "company": target_name,
                            "title": title or item["title"],
                            "url": url,
                            "relevance": relevance,
                            "snippet": norm[:300],
                            "priority": target.get("priority"),
                            "fit_notes": target.get("fit_notes"),
                        })
                    except Exception:
                        results.append({
                            "company": target_name,
                            "title": item["title"],
                            "url": url,
                            "relevance": item["relevance"],
                            "snippet": "",
                        })

                results.sort(key=lambda x: x["relevance"], reverse=True)
                all_results.extend(results)
    finally:
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()

    all_results.sort(key=lambda x: x["relevance"], reverse=True)
    return all_results[:max_results]
