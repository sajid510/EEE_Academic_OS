# 📚 EEE Academic OS

A hybrid **AI tutor + study-performance tracker + deadline manager** for EEE
undergraduates — built with Streamlit and your own Google Workspace.

![EEE Academic OS](assets/app-screenshot.png)

> Hybrid AI + Performance + Deadlines — all in one dashboard.

---

## ✨ What it does

| Tab | What you get |
|---|---|
| 📊 **Dashboard** | Mastery by course, practice trend, score-vs-time scatter, GPA estimate, weekly streak |
| 📅 **Deadlines** | Upcoming calendar events with day-countdowns and one-click **prep blocks** (3 days before, 18:00) |
| 🧠 **AI Tutor** | Gemini 2.5 Flash tutoring grounded in your Google Docs notes, with chat history and `[From Notes]` / `[Added Knowledge]` labels |
| ✍️ **Log Session** | Log a study session (course, topic, score, time, notes) → appended to your `Performance_Log` sheet |
| ⚙️ **Performance** | Weak topics (< 60 avg), strong topics, full session log |
| 🧠 **Learning** | The AI's self-training memory: preferences, 👍/👎 ratings, DO/AVOID corrections, export/restore |
| 📤 **Export** | One-click CSV download of all performance data |

It runs in **demo mode with sample data** until you add your Google
credentials — so every feature is explorable before you connect anything.

---

## 🚀 Quick start

### Demo (no Google account needed)

```bash
pip install -r requirements.txt
streamlit run app.py
```

You'll see the app in demo mode with seeded sample data.

### Go live with your Google account

1. Create a service account in Google Cloud, enable **Sheets, Calendar, Drive,
   and Docs APIs**, and share your `Performance_Log` spreadsheet with the
   service-account email.
2. Get a **Gemini API key** from Google AI Studio.
3. Create `.streamlit/secrets.toml` (git-ignored):

```toml
GEMINI_API_KEY = "your-key"

[gcp_service_account]
type = "service_account"
project_id = "your-project"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

4. Restart: `streamlit run app.py` → sidebar shows **Live · Google connected**.

### Codespaces / devcontainer

Open in GitHub Codespaces (or VS Code Remote — Containers) and the
`postAttachCommand` launches the app on port 8501 automatically.

---

## 📊 Performance_Log sheet schema

The sheet (default name `Performance_Log`) should have these columns:

| Date | Course | Topic | Practice Score | Time Spent | Notes |
|---|---|---|---|---|---|
| 2026-07-20 | Electronics I | BJT Amplifiers | 78 | 2.5 | bias point review |

- **Practice Score** — 0–100 quiz/practice mark.
- **Time Spent** — hours studying that topic.
- The **Log Session** tab writes this schema for you.

### Scoring model

```
Mastery Score = 0.7 × Practice Score + 0.3 × min(100, 20 × Time Hours)
Est. GPA      = mean(Score) / 100 × 4.0
Weak topic    = average score below 60
```

---

## 🧠 Self-learning AI tutor

The tutor **gets better with every session** by remembering your behaviour —
entirely free, stored locally as `memory/memory.json` (git-ignored).

- **Rate every answer** 👍 / 👎 after a chat — the tutor tracks your approval.
- **Correct it** with a note like *"use a circuit diagram"* or *"shorter
  steps"* — these become DO/AVOID rules.
- **Set preferences** (style, difficulty, focus) in the AI Tutor tab.
- **Weak topics** from your performance data are injected into every prompt,
  so the tutor explains your weakest areas first.

Before each answer, the app builds a **personalization context** and merges it
into the Gemini system prompt, e.g.:

> *Style: concise. Difficulty: balanced. Primary focus: weak topics. The
> student is weakest in: Circuit Theory — Transient Analysis, … Learned
> DO/AVOID rules from past feedback: «always show units».*

The **Learning tab** shows what it has learned and lets you export/restore the
memory as JSON for backup.

---

## 🗂 Repository structure

```
EEE_Academic_OS/
├── app.py                  # Streamlit application (entry point)
├── dashboard.py            # legacy entry shim (streamlit run dashboard.py)
├── src/
│   ├── config.py           # all tunable settings
│   ├── analytics.py        # pure study analytics (unit-tested)
│   ├── gemini.py           # AI tutor prompt builder + API call
│   ├── learning.py         # self-learning tutor memory (preferences, feedback)
│   ├── services.py         # Google Sheets/Calendar/Docs integration
│   └── sample_data.py      # deterministic demo data
├── memory/                 # local tutor memory (git-ignored, exportable)
├── tests/                  # pytest suite (34 tests)
├── .streamlit/config.toml  # dark theme + headless server
├── .devcontainer/          # Codespaces setup
├── .github/workflows/tests.yml
├── assets/                 # architecture.svg + app screenshot
├── docs/ARCHITECTURE.md    # design document
└── requirements.txt
```

---

## 🧪 Testing

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

The suite covers the analytics core (mastery, GPA, topics, streaks, prep
blocks) and the AI-tutor prompt builder. CI runs it on Python 3.10–3.12.

---

## 🔒 Security

- **No secrets in code** — API keys and the service account live only in
  `.streamlit/secrets.toml` (git-ignored) or your hosting platform's secrets.
- **Scoped credentials** — the service account is limited to the scopes in
  `src/config.py` (sheets, drive, calendar, docs read-only).
- **Graceful degradation** — missing secrets start demo mode; failed service
  calls fall back cleanly instead of crashing.

---

## 📜 License

MIT — see [`LICENSE`](LICENSE).
