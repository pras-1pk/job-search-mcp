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
Senior Cloud Engineer at LTIMindtree — deployed at Google LLC on DV360 ad platform

Core Stack: Python, FastAPI, GCP, Pub/Sub, Cloud Tasks, Cloud Run,
Firestore, Redis, BigQuery, Vertex AI, Gemini 2.5 Pro, AlloyDB pgvector,
Docker, Kubernetes, GitLab CI/CD, Terraform, MCP (FastMCP)

Key Projects:

- DV360 targeting upload pipeline (Google LLC): Pub/Sub-driven event pipeline,
  Cloud Tasks queuing, Saga compensation, Firestore idempotency, 50K+ events/day,
  multi-region GCP deployment. Cut end-to-end latency by 70%, API response by 50%.

- Redis token caching (Google LLC): Cache-aside pattern, TTL jitter, GCP Memorystore
  with App Engine VPC peering. Reduced token retrieval from 2s → 1ms (99.95% reduction),
  eliminated 50K+ redundant downstream API calls per day.

- Multimodal RAG pipeline (LTIMindtree): Vertex AI + Gemini 2.5 Pro, layout-based
  chunking with overlap, Gemini Embedding 2 (768-d), AlloyDB pgvector (single-row schema,
  zero joins), BDD test generation. Eliminated 4-6 hours manual test authoring per sprint.

- NL-to-SQL alerting platform (Dentsu): Vertex AI SQL generation, two-layer validation
  (syntax parsing + BigQuery dry-run), Firestore runtime config, 1000+ analyst clients,
  zero SQL knowledge required by end users.

- Job search MCP server: FastMCP-based MCP server exposing search_jobs, analyse_job,
  track_job tools. Claude Desktop integration, GCP Secret Manager, Gemini 2.5 Flash
  structured output, keyword prefiltering to reduce inference costs.

- Job search automation agent: GCP Cloud Run, Cloud Scheduler, Gemini scoring,
  JSearch API, Google Sheets tracking, Telegram delivery. Reduced daily search
  overhead from 1 hour to 5 minutes. Cost: ~$0.03/month.

System Design: Event-driven architecture, distributed systems, async job processing,
fan-out pipelines, Pub/Sub patterns, idempotency, Saga compensation pattern,
cache-aside strategy, Redis, database sharding, microservices, rate limiting,
agentic workflows, MCP server design.

AI/ML: Vertex AI, Gemini API (2.5 Pro, Embedding 2), RAG pipelines, semantic chunking,
vector search (AlloyDB pgvector), HNSW indexing, agentic workflows, MCP.
"""