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
from src.learning import TutorMemory


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

# ── Learning memory (self-training) ─────────────────────────────────────────
if "tutor_memory" not in st.session_state:
    st.session_state.tutor_memory = TutorMemory()

memory = st.session_state.tutor_memory

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
    "🧠 Learning",
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
        st.bar_chart(course_mastery.set_index(analytics.COURSE_COL))

        st.markdown("#### Practice trend")
        trend = analytics.trend_series(frame)
        if not trend.empty:
            trend[analytics.DATE_COL] = trend[analytics.DATE_COL].dt.strftime("%m-%d")
            st.line_chart(trend.set_index(analytics.DATE_COL)[analytics.SCORE_COL])

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

    # ── Learning preferences ────────────────────────────────────────────────
    with st.expander("🧠 Tutor preferences (the AI learns these)"):
        c1, c2, c3 = st.columns(3)
        style = c1.selectbox("Style", ["concise", "balanced", "detailed"],
                             index=["concise", "balanced", "detailed"].index(memory.data["preferences"].get("style", "balanced")),
                             key="pref_style")
        difficulty = c2.selectbox("Difficulty", ["gentle", "balanced", "advanced"],
                                  index=["gentle", "balanced", "advanced"].index(memory.data["preferences"].get("difficulty", "balanced")),
                                  key="pref_diff")
        focus = c3.selectbox("Primary focus", ["weak topics", "exam prep", "deep understanding", "quick review"],
                             index=["weak topics", "exam prep", "deep understanding", "quick review"].index(memory.data["preferences"].get("focus", "weak topics")),
                             key="pref_focus")
        if st.button("Save preferences"):
            memory.set_preference("style", style)
            memory.set_preference("difficulty", difficulty)
            memory.set_preference("focus", focus)
            memory.save()
            st.success("Preferences saved — future answers will follow them.")

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

            # Personalization context from the learned memory + analytics
            weak = [f"{r[analytics.COURSE_COL]} — {r[analytics.TOPIC_COL]}"
                    for r in analytics.weak_topics(frame).head(3).to_dict("records")]
            personalization = memory.personalization_context(
                weak_topics=weak, courses=memory.preferred_courses(3)
            )

            answer = gemini.ask_gemini(
                question=question.strip(),
                notes=notes,
                api_key=st.secrets.get("GEMINI_API_KEY", "") if _has_secrets() else "",
                history=st.session_state.chat,
                personalization=personalization,
            )

        st.session_state.chat.append({"role": "user", "content": question.strip()})
        st.session_state.chat.append({"role": "assistant", "content": answer})
        st.session_state.last_answer = answer
        st.session_state.last_question = question.strip()
        st.session_state.show_feedback = True

        st.markdown("**🤖 Tutor:**")
        st.markdown(answer)

    # ── Rating / correction feedback loop ───────────────────────────────────
    if st.session_state.get("show_feedback") and st.session_state.get("last_answer"):
        st.markdown("---")
        st.markdown("**Did this answer help?** *(the tutor learns from your feedback)*")
        rc1, rc2, rc3 = st.columns([1, 1, 3])
        if rc1.button("👍 Good", key="rate_good"):
            memory.record_interaction(
                st.session_state.last_question,
                st.session_state.last_answer,
                course=st.session_state.get("last_course", ""),
                topic=st.session_state.get("last_topic", ""),
                rating=1,
            )
            st.session_state.show_feedback = False
            st.rerun()
        if rc2.button("👎 Needs work", key="rate_bad"):
            memory.record_interaction(
                st.session_state.last_question,
                st.session_state.last_answer,
                course=st.session_state.get("last_course", ""),
                topic=st.session_state.get("last_topic", ""),
                rating=-1,
            )
            st.session_state.show_feedback = False
            st.rerun()
        with rc3:
            correction = st.text_input(
                "Optional: what should the AI do differently? (e.g. 'use a "
                "circuit diagram', 'shorter steps')",
                key="correction_input",
            )
            if st.button("Save correction", key="save_correction"):
                memory.record_interaction(
                    st.session_state.last_question,
                    st.session_state.last_answer,
                    course=st.session_state.get("last_course", ""),
                    topic=st.session_state.get("last_topic", ""),
                    correction=correction,
                )
                st.session_state.show_feedback = False
                st.success("Correction saved — the tutor will avoid this next time.")
                st.rerun()


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
# 6. Learning
# ══════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("AI Learning Memory")

    m = memory.stats()
    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.metric("Tutor sessions", m["sessions"])
    lc2.metric("Ratings given", m["ratings"])
    lc3.metric("Avg rating", f"{m['avg_rating']:.2f}" if m["avg_rating"] else "—")
    lc4.metric("Learned rules", m["corrections"])

    st.markdown("#### Learned preferences")
    prefs = m["preferences"]
    st.json({
        "style": prefs.get("style"),
        "difficulty": prefs.get("difficulty"),
        "focus": prefs.get("focus"),
        "courses": prefs.get("courses", [])[-5:],
    })

    st.markdown("#### Personalization context (injected into every AI prompt)")
    weak = [f"{r[analytics.COURSE_COL]} — {r[analytics.TOPIC_COL]}"
            for r in analytics.weak_topics(frame).head(3).to_dict("records")]
    st.info(memory.personalization_context(weak_topics=weak,
                                           courses=memory.preferred_courses(3)))

    if m["corrections"]:
        st.markdown("#### DO/AVOID rules you taught it")
        st.dataframe(pd.DataFrame(memory.data["corrections"][-10:])[["ts", "rule"]],
                     use_container_width=True)

    st.markdown("---")
    st.markdown("#### Backup & restore (free)")
    st.download_button(
        "⬇️ Download learning memory (JSON)",
        data=memory.export_json(),
        file_name=f"eee-tutor-memory-{dt.date.today().isoformat()}.json",
        mime="application/json",
    )
    uploaded = st.file_uploader("Restore a memory backup", type=["json"])
    if uploaded is not None:
        try:
            memory.import_json(uploaded.read().decode("utf-8"))
            st.success("Learning memory restored.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not restore memory: {exc}")


# ══════════════════════════════════════════════════════════════════════════
# 7. Export
# ══════════════════════════════════════════════════════════════════════════
with tabs[6]:
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
