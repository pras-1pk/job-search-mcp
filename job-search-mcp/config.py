# config.py
import os

"""Configuration and secret loading.

This module attempts to read secrets from Secret Manager first. If that
fails (e.g., no GCP credentials available), it falls back to environment
variables to preserve local developer experience.
"""

def _access_secret(secret_name: str) -> str | None:
	try:
		from google.cloud import secretmanager
		from google.auth import default as google_auth_default

		_, project = google_auth_default()
		# project = os.getenv("GCP_PROJECT")  # Optional override for local dev
		client = secretmanager.SecretManagerServiceClient()
		name = f"projects/{project}/secrets/{secret_name}/versions/latest"
		resp = client.access_secret_version(request={"name": name})
		print(f"✓ Loaded {secret_name} from Secret Manager", file=__import__('sys').stderr)
		return resp.payload.data.decode("utf-8")
	except Exception as e:
		print(f"✗ Secret Manager failed for {secret_name}: {e}", file=__import__('sys').stderr)
		return None


JSEARCH_API_KEY = _access_secret("JSEARCH_API_KEY") or os.getenv("JSEARCH_API_KEY")
GEMINI_API_KEY = _access_secret("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
SHEETS_ID = _access_secret("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
# Optional: service account email for impersonation
SHEETS_SERVICE_ACCOUNT = _access_secret("SHEETS_SERVICE_ACCOUNT") or os.getenv("SHEETS_SERVICE_ACCOUNT")

RESUME_TEXT = """
Backend Engineer | 4 years production experience | M.Tech IIT Guwahati
Deployed at Google LLC on DV360 ad platform (LTIMindtree)

Core Stack: Python, FastAPI, GCP, Pub/Sub, Cloud Tasks, Cloud Run,
Firestore, Redis, BigQuery, Vertex AI, Gemini 2.5 Pro, AlloyDB,
Docker, GitLab CI/CD, Terraform

Key Projects:
- DV360 targeting upload pipeline: Pub/Sub + Cloud Tasks, Saga compensation,
  Firestore idempotency, 50K+ events/day, multi-region GCP
- Redis token caching: cache-aside, TTL jitter, 99.95% latency reduction
- Multimodal RAG pipeline: Vertex AI + Gemini 2.5 Pro, layout-based chunking,
  AlloyDB pgvector, BDD test generation, 80% effort reduction
- NL-to-SQL alerting platform: Vertex AI SQL generation, two-layer validation,
  BigQuery dry-run, 1000+ analyst clients
- Job search automation agent: GCP Cloud Run, Gemini scoring, Sheets tracking

Skills: Distributed systems, event-driven architecture, AI/ML production systems,
RAG pipelines, vector search, MCP, asyncio, OOPs, system design
"""