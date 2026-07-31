"""Google services integration (Sheets, Calendar, Drive, Docs).

Every function degrades gracefully: when credentials are missing or a service
call fails, the app falls back to demo mode instead of crashing.
"""

from datetime import datetime, timedelta

import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

from src import config


def credentials_from_secrets(secrets):
    """Build Google service-account credentials from Streamlit secrets."""
    info = secrets.get("gcp_service_account")
    if not info:
        raise ValueError("Google service account missing in secrets")
    return Credentials.from_service_account_info(info, scopes=config.SCOPES)


def read_performance(credentials, sheet_name=None):
    """Read the Performance_Log sheet into a DataFrame (empty df on failure)."""
    try:
        gc = gspread.authorize(credentials)
        sheet = gc.open(sheet_name or config.SHEET_NAME).sheet1
        records = sheet.get_all_records()
        return pd.DataFrame(records) if records else pd.DataFrame()
    except Exception as exc:
        print(f"[services] read_performance failed: {exc}")
        return pd.DataFrame()


def append_session(credentials, row, sheet_name=None):
    """Append one study-session row to the sheet. Returns bool success."""
    try:
        gc = gspread.authorize(credentials)
        sheet = gc.open(sheet_name or config.SHEET_NAME).sheet1
        sheet.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as exc:
        print(f"[services] append_session failed: {exc}")
        return False


def list_events(credentials, calendar_id=None, days=None):
    """List upcoming calendar events within the lookahead window."""
    days = days or config.CALENDAR_LOOKAHEAD_DAYS
    try:
        service = build("calendar", "v3", credentials=credentials)
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
        result = (
            service.events()
            .list(
                calendarId=calendar_id or config.CALENDAR_ID,
                timeMin=now,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])
    except Exception as exc:
        print(f"[services] list_events failed: {exc}")
        return []


def create_prep_block(credentials, event, calendar_id=None):
    """Create a prep-block event before a deadline. Returns bool success."""
    try:
        start_raw = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        start_dt = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        prep_start, prep_end = prep_window(start_dt)

        body = {
            "summary": f"📚 Prep: {event.get('summary', 'Deadline')}",
            "start": {"dateTime": prep_start.isoformat()},
            "end": {"dateTime": prep_end.isoformat()},
        }
        service = build("calendar", "v3", credentials=credentials)
        service.events().insert(
            calendarId=calendar_id or config.CALENDAR_ID, body=body
        ).execute()
        return True
    except Exception as exc:
        print(f"[services] create_prep_block failed: {exc}")
        return False


def prep_window(event_dt):
    """Return (start, end) datetimes for a prep block before a deadline."""
    from src.analytics import prep_block  # local import avoids a circular dep

    start, end = prep_block(event_dt)
    if start.tzinfo is None:
        # Emit UTC for Google Calendar consistency.
        start = start.replace(tzinfo=__import__("datetime").timezone.utc)
        end = end.replace(tzinfo=__import__("datetime").timezone.utc)
    return start, end


def fetch_notes(credentials, limit=10):
    """Fetch text from Drive docs whose name matches Notes/Formula/Question."""
    try:
        drive_service = build("drive", "v3", credentials=credentials)
        docs_service = build("docs", "v1", credentials=credentials)

        query = "name contains 'Notes' or name contains 'Formula' or name contains 'Question'"
        files = (
            drive_service.files().list(q=query, pageSize=limit).execute().get("files", [])
        )

        full_text = []
        for file in files:
            try:
                document = docs_service.documents().get(documentId=file["id"]).execute()
                text = _extract_doc_text(document)
                if text.strip():
                    full_text.append(f"--- {file.get('name', 'doc')} ---\n{text.strip()}")
            except Exception:
                continue
        return "\n\n".join(full_text)
    except Exception as exc:
        print(f"[services] fetch_notes failed: {exc}")
        return ""


def _extract_doc_text(document):
    text = []
    for content in document.get("body", {}).get("content", []):
        if "paragraph" in content:
            for element in content["paragraph"].get("elements", []):
                run = element.get("textRun")
                if run:
                    text.append(run.get("content", ""))
    return "".join(text)
