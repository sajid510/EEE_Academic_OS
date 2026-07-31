"""EEE Academic OS — Streamlit application.

Hybrid AI + performance tracking + deadline management for an EEE student.

Run:
    streamlit run app.py

Without Streamlit secrets the app starts in **demo mode** with sample data so
every feature is explorable without a Google account.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from src import config, analytics, services, gemini, sample_data


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════
def _has_secrets():
    try:
        return ("gcp_service_account" in st.secrets) and ("GEMINI_API_KEY" in st.secrets)
    except Exception:
        return False


def _credentials():
    try:
        return services.credentials_from_secrets(st.secrets)
    except Exception as exc:
        st.error(f"Could not build Google credentials: {exc}")
        return None


def _load_data():
    """Return (dataframe, live:bool)."""
    if _has_secrets():
        creds = _credentials()
        if creds is not None:
            df = services.read_performance(creds)
            if not df.empty:
                return df, True
    return sample_data.sample_performance(), False


# ══════════════════════════════════════════════════════════════════════════
# Page config
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title=config.APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title(f"📚 {config.APP_TITLE}")
st.markdown(f"*{config.APP_SUBTITLE}*")

data, live = _load_data()
frame = analytics.add_mastery(data)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧭 Status")
    if live:
        st.success("Live · Google connected")
    else:
        st.warning("Demo mode · sample data (add secrets for live data)")
    summary = analytics.summarize(frame)
    st.metric("Est. GPA", f"{summary['gpa_estimate']:.2f} / 4.00")
    st.metric("Sessions logged", summary["sessions"])
    st.metric("Weekly streak", f"{summary['streak']} week(s)")
    st.caption("Add `gcp_service_account` + `GEMINI_API_KEY` to "
               "`.streamlit/secrets.toml` to go live.")

tabs = st.tabs([
    "📊 Dashboard",
    "📅 Deadlines",
    "🧠 AI Tutor",
    "✍️ Log Session",
    "⚙️ Performance",
    "📤 Export",
])


# ══════════════════════════════════════════════════════════════════════════
# 1. Dashboard
# ══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("Mastery Overview")

    if frame.empty:
        st.info("No performance data available. Use the **Log Session** tab "
                "to add your first study session.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mean Mastery", f"{summary['mean_mastery']:.1f}/100")
        c2.metric("Mean Practice Score", f"{summary['mean_score']:.1f}/100")
        c3.metric("Courses tracked", summary["courses"])
        c4.metric("Weak topics", summary["weak_topics"])

        st.markdown("#### Mastery by course")
        course_mastery = analytics.topic_mastery(frame)
        st.bar_chart(course_mastery.set_index(config.COURSE_COL))

        st.markdown("#### Practice trend")
        trend = analytics.trend_series(frame)
        if not trend.empty:
            trend[config.DATE_COL] = trend[config.DATE_COL].dt.strftime("%m-%d")
            st.line_chart(trend.set_index(config.DATE_COL)[analytics.SCORE_COL])

        st.markdown("#### Score vs time invested")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.scatter(frame[analytics.TIME_COL], frame[analytics.SCORE_COL],
                   c="#7c6af7", alpha=0.7)
        ax.set_xlabel("Time spent (hours)")
        ax.set_ylabel("Practice score")
        ax.set_title("Time vs Practice Score")
        st.pyplot(fig)


# ══════════════════════════════════════════════════════════════════════════
# 2. Deadlines
# ══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Upcoming Deadlines")

    if not live:
        st.info("Connect Google Calendar (via secrets) to see your live "
                "deadlines. Showing a preview from sample data below.")
        sample_events = [
            {"summary": "Circuit Theory Assignment 3", "start": {"date": (dt.date.today() + dt.timedelta(days=3)).isoformat()}},
            {"summary": "Signals & Systems Quiz", "start": {"date": (dt.date.today() + dt.timedelta(days=7)).isoformat()}},
            {"summary": "Digital Logic Lab Report", "start": {"date": (dt.date.today() + dt.timedelta(days=12)).isoformat()}},
        ]
        events = sample_events
    else:
        creds = _credentials()
        events = services.list_events(creds) if creds else []

    lookahead = st.select_slider("Window", options=[7, 14, 30], value=config.CALENDAR_LOOKAHEAD_DAYS)

    if not events:
        st.success("No upcoming deadlines in the next 14 days 🎉")
    else:
        now = dt.datetime.now()
        rows = []
        for i, event in enumerate(events):
            start_raw = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
            try:
                start_dt = dt.datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            except ValueError:
                start_dt = now + dt.timedelta(days=1)
            if (start_dt - now).days > lookahead:
                continue
            rows.append((event, start_dt, i))

        for event, start_dt, i in sorted(rows, key=lambda r: r[1]):
            days = (start_dt - now).days
            when = f"**{days} day(s) away**" if days >= 0 else f"*{abs(days)} day(s) overdue*"
            title = event.get("summary", "No Title")
            st.markdown(f"### 📌 {title}")
            st.markdown(f"{when} · due {start_dt.strftime('%a, %d %b %Y %H:%M')}")

            if st.button(f"Block prep (3 days before)", key=f"prep_{i}_{title[:20]}"):
                if live:
                    ok = services.create_prep_block(creds, event)
                    st.success("Prep block added to your calendar ✅") if ok else st.error("Could not add prep block.")
                else:
                    st.info("Connect your calendar to add real prep blocks. "
                            f"(Preview: prep on {start_dt.date() - dt.timedelta(days=config.PREP_DAYS_BEFORE)} at 18:00)")

    st.markdown("---")
    st.caption(f"Prep blocks are auto-scheduled {config.PREP_DAYS_BEFORE} days "
               f"before each deadline, {config.PREP_HOUR}:00–{config.PREP_HOUR + config.PREP_DURATION_HOURS}:00.")


# ══════════════════════════════════════════════════════════════════════════
# 3. AI Tutor
# ══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Hybrid AI Tutor (Gemini)")

    if not live:
        st.info("Connect your Google account + Gemini key for full note-aware "
                "tutoring. Answering with general knowledge in demo mode.")

    if "chat" not in st.session_state:
        st.session_state.chat = []

    for turn in st.session_state.chat:
        role = "🧑‍🎓 You" if turn["role"] == "user" else "🤖 Tutor"
        st.markdown(f"**{role}:**")
        st.markdown(turn["content"])
        st.divider()

    with st.form("tutor_form", clear_on_submit=True):
        question = st.text_area("Ask your academic question", key="tutor_question")
        with_context = st.checkbox("Include my Google Docs notes", value=True)
        submitted = st.form_submit_button("Ask AI")

    if submitted and question.strip():
        with st.spinner("Analyzing notes and generating response..."):
            notes = ""
            if live and with_context:
                creds = _credentials()
                if creds is not None:
                    notes = services.fetch_notes(creds)
            elif not with_context:
                notes = ""

            answer = gemini.ask_gemini(
                question=question.strip(),
                notes=notes,
                api_key=st.secrets.get("GEMINI_API_KEY", "") if _has_secrets() else "",
                history=st.session_state.chat,
            )

        st.session_state.chat.append({"role": "user", "content": question.strip()})
        st.session_state.chat.append({"role": "assistant", "content": answer})

        st.markdown("**🤖 Tutor:**")
        st.markdown(answer)


# ══════════════════════════════════════════════════════════════════════════
# 4. Log Session
# ══════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("Log a Study Session")

    if not live:
        st.info("Demo mode — your session won't be saved. Connect Google "
                "Sheets to persist entries to the Performance_Log sheet.")

    with st.form("session_form"):
        col1, col2 = st.columns(2)
        with col1:
            session_date = st.date_input("Date", value=dt.date.today())
            course = st.selectbox("Course", config.COURSE_OPTIONS)
        with col2:
            topic = st.text_input("Topic")
            practice_score = st.slider("Practice Score (0-100)", 0, 100, 60)
            time_spent = st.slider("Time Spent (hours)", 0.0, 8.0, 1.0, 0.5)
        notes = st.text_area("Notes (optional)", height=80)
        submitted = st.form_submit_button("Save Session")

    if submitted:
        row = [
            session_date.isoformat(),
            course,
            topic or course,
            int(practice_score),
            float(time_spent),
            notes,
        ]
        if live:
            creds = _credentials()
            ok = services.append_session(creds, row) if creds else False
            if ok:
                st.success("Session saved to Performance_Log ✅")
            else:
                st.error("Could not save session.")
        else:
            st.session_state.setdefault("demo_sessions", []).append(row)
            st.success("Demo session recorded (shown in Performance view this run)")

    if "demo_sessions" in st.session_state and st.session_state.demo_sessions:
        st.markdown("#### Sessions logged this session (demo)")
        st.dataframe(pd.DataFrame(st.session_state.demo_sessions,
                                  columns=analytics.REQUIRED_COLUMNS + [analytics.NOTES_COL]))


# ══════════════════════════════════════════════════════════════════════════
# 5. Performance
# ══════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Weak Topics (avg score < 60)")

    if frame.empty:
        st.info("No data available.")
    else:
        weak = analytics.weak_topics(frame)
        if weak.empty:
            st.success("No weak topics — great job! 🎉")
        else:
            st.dataframe(weak, use_container_width=True)

        st.markdown("#### Strong topics")
        strong = analytics.strong_topics(frame)
        st.dataframe(strong, use_container_width=True)

        st.markdown("#### Full log")
        st.dataframe(frame.sort_values(analytics.DATE_COL, ascending=False),
                     use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# 6. Export
# ══════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("Export Data")

    if frame.empty:
        st.info("No data to export.")
    else:
        csv = frame.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download performance data (CSV)",
            data=csv,
            file_name=f"eee-performance-{dt.date.today().isoformat()}.csv",
            mime="text/csv",
        )
        st.markdown("#### Backup & restore")
        st.caption("Keep a copy of your Performance_Log anywhere. To restore, "
                   "import the CSV rows back into the Google Sheet.")
