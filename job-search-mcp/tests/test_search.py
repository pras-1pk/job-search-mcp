import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from tools.search import _greenhouse_apply_url, is_fresh, is_link_alive, search_jobs


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json_data


class SearchTests(unittest.TestCase):
    def test_greenhouse_apply_url_uses_job_boards_format(self):
        url = _greenhouse_apply_url("postman", {"id": "12345"})

        self.assertEqual(url, "https://job-boards.greenhouse.io/postman/jobs/12345")

    def test_is_fresh_accepts_recent_jobs(self):
        posted = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat().replace("+00:00", "Z")

        self.assertTrue(is_fresh(posted, max_days=14))

    def test_is_fresh_rejects_old_jobs(self):
        posted = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")

        self.assertFalse(is_fresh(posted, max_days=14))

    def test_search_jobs_filters_dead_and_old_jobs(self):
        fake_response = FakeResponse(status_code=200, json_data={
            "data": [
                {"job_title": "Fresh Backend", "employer_name": "Acme", "job_city": "Bengaluru", "job_description": "desc", "job_apply_link": "https://example.com/open", "job_posted_at_datetime_utc": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")},
                {"job_title": "Old Backend", "employer_name": "Acme", "job_city": "Bengaluru", "job_description": "desc", "job_apply_link": "https://example.com/old", "job_posted_at_datetime_utc": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")},
            ]
        })

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=None)
        fake_client.get = AsyncMock(return_value=fake_response)

        with patch("tools.search.httpx.AsyncClient", return_value=fake_client), \
             patch("tools.search.is_link_alive", AsyncMock(side_effect=lambda url: url.endswith("open"))):
            import asyncio
            jobs = asyncio.run(search_jobs("backend", "India"))

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Fresh Backend")


class SearchATSIntegrationTests(unittest.TestCase):
    def test_search_jobs_prefers_ats_for_whitelisted_companies(self):
        fake_ats_jobs = [
            {
                "title": "Backend Engineer",
                "company": "Postman",
                "location": "Bengaluru",
                "description": "Backend role",
                "apply_link": "https://boards.greenhouse.io/postman/jobs/123",
                "posted": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            }
        ]

        with patch("tools.search.fetch_ats_jobs", AsyncMock(return_value=fake_ats_jobs)) as fetch_mock, \
             patch("tools.search.is_link_alive", AsyncMock(return_value=True)), \
             patch("tools.search.httpx.AsyncClient") as client_mock:
            import asyncio
            jobs = asyncio.run(search_jobs("postman backend", "India"))

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Postman")
        fetch_mock.assert_awaited_once_with("postman", "India")
        client_mock.assert_not_called()


class SearchAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_is_link_alive_returns_false_for_dead_links(self):
        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=None)
        fake_client.head = AsyncMock(return_value=FakeResponse(status_code=404))

        with patch("tools.search.httpx.AsyncClient", return_value=fake_client):
            result = await is_link_alive("https://example.com/old")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
