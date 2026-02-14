import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import gspread
import json

st.set_page_config(page_title="EEE Academic OS", layout="wide")
st.title("📚 EEE Academic Operating System")

# =========================
# LOAD SERVICE ACCOUNT
# =========================
with open("service_account.json") as f:
    creds_dict = json.load(f)

GEMINI_API_KEY = "***REDACTED-GOOGLE-API-KEY***"

# =========================
# GOOGLE SHEETS
# =========================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
gc = gspread.authorize(creds)
sheet = gc.open("Performance_Log").sheet1
data = pd.DataFrame(sheet.get_all_records())

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard",
    "📅 Deadlines",
    "🧠 AI Tutor",
    "⚙ Performance"
])

# =========================
# DASHBOARD
# =========================
with tab1:
    st.subheader("Mastery Overview")

    if not data.empty:
        data['Mastery Score'] = (
            data['Practice Score'] * 0.7 +
            (1 / (data['Time Spent'] + 1)) * 30
        )
        st.bar_chart(data[['Mastery Score']])
        predicted_gpa = data['Practice Score'].mean() / 25
        st.metric("Estimated GPA", round(predicted_gpa, 2))

# =========================
# DEADLINES
# =========================
with tab2:
    creds_calendar = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build('calendar', 'v3', credentials=creds_calendar)

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=14)).isoformat() + 'Z'

    events = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=future,
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    for event in events:
        title = event['summary']
        start = event['start'].get('dateTime', event['start'].get('date'))
        st.write(f"**{title}** — {start}")

        if st.button(f"Block Prep for {title}", key=title):
            start_dt = datetime.datetime.fromisoformat(start.replace("Z",""))
            prep_start = start_dt - datetime.timedelta(days=1)
            prep_start = prep_start.replace(hour=18, minute=0)
            prep_end = prep_start + datetime.timedelta(hours=2)

            prep_event = {
                'summary': f'📚 Prep: {title}',
                'start': {'dateTime': prep_start.isoformat(), 'timeZone': 'UTC'},
                'end': {'dateTime': prep_end.isoformat(), 'timeZone': 'UTC'}
            }

            service.events().insert(calendarId='primary', body=prep_event).execute()
            st.success("Prep block added!")

# =========================
# FETCH NOTES
# =========================
def get_notes():
    creds_drive = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/documents.readonly"
        ]
    )

    drive = build('drive', 'v3', credentials=creds_drive)
    results = drive.files().list(q="name contains 'Notes'", pageSize=10).execute()
    files = results.get('files', [])

    full_text = ""

    for file in files:
        docs = build('docs', 'v1', credentials=creds_drive)
        doc = docs.documents().get(documentId=file['id']).execute()
        for content in doc.get('body', {}).get('content', []):
            if 'paragraph' in content:
                for element in content['paragraph'].get('elements', []):
                    if 'textRun' in element:
                        full_text += element['textRun']['content']

    return full_text

# =========================
# AI
# =========================
def ask_ai(question, notes):

    prompt = f"""
You are an academic tutor.

NOTES:
{notes}

QUESTION:
{question}

Rules:
1. Prioritize notes.
2. If missing info, use general knowledge.
3. Clearly mark [From Notes] or [Added Knowledge].
"""

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    response = requests.post(url, json=payload)
    result = response.json()

    return result["candidates"][0]["content"]["parts"][0]["text"]

with tab3:
    question = st.text_input("Ask AI")
    if st.button("Submit"):
        notes = get_notes()
        answer = ask_ai(question, notes)
        st.write(answer)

with tab4:
    weak = data[data['Practice Score'] < 60]
    st.dataframe(weak)
