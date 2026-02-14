import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import gspread

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="EEE Academic OS",
    layout="wide"
)

st.title("📚 EEE Academic Operating System")
st.markdown("Hybrid AI + Performance + Deadlines")

# ==========================================================
# LOAD SECRETS (PRODUCTION SAFE)
# ==========================================================
if "gcp_service_account" not in st.secrets:
    st.error("Google Service Account not configured in Streamlit Secrets.")
    st.stop()

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Gemini API key missing in Streamlit Secrets.")
    st.stop()

GEMINI_API_KEY = st.secrets["***REDACTED-GOOGLE-API-KEY***"]

# ==========================================================
# GOOGLE CREDENTIALS
# ==========================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents.readonly"
]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)

# ==========================================================
# CONNECT TO GOOGLE SHEETS
# ==========================================================
gc = gspread.authorize(credentials)

try:
    sheet = gc.open("Performance_Log").sheet1
    data = pd.DataFrame(sheet.get_all_records())
except Exception as e:
    st.error("Could not connect to Performance_Log sheet.")
    st.stop()

# ==========================================================
# CREATE TABS
# ==========================================================
tab_dashboard, tab_deadlines, tab_ai, tab_performance = st.tabs([
    "📊 Dashboard",
    "📅 Deadlines",
    "🧠 AI Tutor",
    "⚙ Performance"
])

# ==========================================================
# DASHBOARD TAB
# ==========================================================
with tab_dashboard:
    st.subheader("Mastery Overview")

    if not data.empty:
        data["Practice Score"] = pd.to_numeric(data["Practice Score"], errors="coerce")
        data["Time Spent"] = pd.to_numeric(data["Time Spent"], errors="coerce")

        data["Mastery Score"] = (
            data["Practice Score"] * 0.7 +
            (1 / (data["Time Spent"] + 1)) * 30
        )

        st.bar_chart(data[["Mastery Score"]])

        predicted_gpa = data["Practice Score"].mean() / 25
        st.metric("Estimated GPA", round(predicted_gpa, 2))

        st.subheader("Time vs Practice Score")
        fig, ax = plt.subplots()
        ax.scatter(data["Time Spent"], data["Practice Score"])
        ax.set_xlabel("Time Spent (hours)")
        ax.set_ylabel("Practice Score")
        st.pyplot(fig)
    else:
        st.info("No performance data available.")

# ==========================================================
# DEADLINES TAB
# ==========================================================
with tab_deadlines:

    st.subheader("Upcoming Deadlines (Next 14 Days)")

    calendar_service = build("calendar", "v3", credentials=credentials)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=14)).isoformat() + "Z"

    events = calendar_service.events().list(
        calendarId="primary",
        timeMin=now,
        timeMax=future,
        singleEvents=True,
        orderBy="startTime"
    ).execute().get("items", [])

    if not events:
        st.info("No upcoming deadlines found.")
    else:
        for event in events:
            title = event.get("summary", "No Title")
            start = event["start"].get("dateTime", event["start"].get("date"))

            st.write(f"**{title}** — {start}")

            if st.button(f"Block Prep for {title}", key=title):

                start_dt = datetime.datetime.fromisoformat(start.replace("Z", ""))

                prep_start = start_dt - datetime.timedelta(days=1)
                prep_start = prep_start.replace(hour=18, minute=0)
                prep_end = prep_start + datetime.timedelta(hours=2)

                prep_event = {
                    "summary": f"📚 Prep: {title}",
                    "start": {
                        "dateTime": prep_start.isoformat(),
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": prep_end.isoformat(),
                        "timeZone": "UTC"
                    }
                }

                calendar_service.events().insert(
                    calendarId="primary",
                    body=prep_event
                ).execute()

                st.success("Prep block added successfully!")

# ==========================================================
# FETCH NOTES FROM GOOGLE DOCS
# ==========================================================
def fetch_notes():

    drive_service = build("drive", "v3", credentials=credentials)
    docs_service = build("docs", "v1", credentials=credentials)

    query = "name contains 'Notes' or name contains 'Formula' or name contains 'Question'"
    results = drive_service.files().list(q=query, pageSize=10).execute()

    files = results.get("files", [])
    full_text = ""

    for file in files:
        try:
            document = docs_service.documents().get(
                documentId=file["id"]
            ).execute()

            for content in document.get("body", {}).get("content", []):
                if "paragraph" in content:
                    for element in content["paragraph"].get("elements", []):
                        if "textRun" in element:
                            full_text += element["textRun"]["content"]
        except:
            continue

    return full_text

# ==========================================================
# GEMINI 2.0 HYBRID AI
# ==========================================================
def ask_gemini(question, notes):

    prompt = f"""
You are an academic tutor.

NOTES:
{notes}

QUESTION:
{question}

Instructions:
1. Prioritize the notes content.
2. If notes do not contain enough information, use general knowledge.
3. Clearly label content sections as:
   [From Notes]
   [Added Knowledge]
4. Be structured and concise.
"""

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    response = requests.post(url, json=payload)

    if response.status_code != 200:
        return "Error communicating with Gemini API."

    result = response.json()

    return result["candidates"][0]["content"]["parts"][0]["text"]

# ==========================================================
# AI TAB
# ==========================================================
with tab_ai:

    st.subheader("Hybrid AI Tutor (Gemini 2.0)")

    question = st.text_input("Ask your academic question")

    if st.button("Ask AI") and question:

        with st.spinner("Analyzing notes and generating response..."):
            notes = fetch_notes()
            answer = ask_gemini(question, notes)

        st.write(answer)

# ==========================================================
# PERFORMANCE TAB
# ==========================================================
with tab_performance:

    st.subheader("Weak Topics (Score < 60)")

    if not data.empty:
        weak = data[pd.to_numeric(data["Practice Score"], errors="coerce") < 60]
        st.dataframe(weak)
    else:
        st.info("No data available.")
