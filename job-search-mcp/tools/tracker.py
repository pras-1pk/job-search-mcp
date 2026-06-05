"""Tracker tool implementation.

This module prefers using service account impersonation (when the
`SHEETS_SERVICE_ACCOUNT` env var is set) to obtain short-lived credentials
for Google Sheets. If that variable is not set it falls back to reading
`service_account.json` for local development.
"""

import os
import gspread
from google.oauth2 import service_account
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request
from google.auth.impersonated_credentials import Credentials as ImpersonatedCredentials
from datetime import datetime
from config import SHEETS_ID, SHEETS_SERVICE_ACCOUNT


def get_sheet():
    """Return the first worksheet from the configured Google Sheet.

    Uses impersonation if `SHEETS_SERVICE_ACCOUNT` is set (recommended).
    Falls back to `service_account.json` if not set (local dev).
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    target_sa = SHEETS_SERVICE_ACCOUNT

    if target_sa:
        source_credentials, project_id = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if hasattr(source_credentials, "refresh"):
            source_credentials.refresh(Request())

        impersonated_creds = ImpersonatedCredentials(
            source_credentials=source_credentials,
            target_principal=target_sa,
            target_scopes=scopes,
            lifetime=3600,
        )

        client = gspread.authorize(impersonated_creds)
        return client.open_by_key(SHEETS_ID).sheet1

    # Fallback for local development: service account key file
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=scopes,
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEETS_ID).sheet1

async def track_job(
    title: str,
    company: str,
    apply_link: str,
    score: int,
    recommendation: str
) -> dict:
    """Add a job to Google Sheets tracker"""
    
    sheet = get_sheet()
    
    # Check duplicate
    existing = sheet.col_values(3)  # apply_link column
    if apply_link in existing:
        return {"status": "duplicate", "message": "Job already tracked"}
    
    # Append row
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        title,
        company,
        apply_link,
        score,
        recommendation,
        "pending"  # application status
    ])
    
    return {"status": "added", "message": f"Tracked: {title} at {company}"}
