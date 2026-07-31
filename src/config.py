"""Central configuration for the EEE Academic OS.

All tunable values live here so the app, analytics, and tests stay consistent.
"""

# ── Google integrations ────────────────────────────────────────────────────
SHEET_NAME = "Performance_Log"          # Google Sheets tab with study data
CALENDAR_ID = "primary"                 # Google Calendar to read / write
CALENDAR_LOOKAHEAD_DAYS = 14            # deadlines window shown by default

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents.readonly",
]

# ── Study analytics ────────────────────────────────────────────────────────
SCORE_WEIGHT = 0.7          # weight of practice score in mastery
TIME_WEIGHT = 0.3           # weight of time factor in mastery
TIME_FACTOR_PER_HOUR = 20   # hours * this → time factor (capped at 100)
MAX_SCORE = 100.0
WEAK_TOPIC_THRESHOLD = 60   # topics averaging below this are "weak"
GPA_SCALE = 4.0             # GPA estimate scale

# ── AI tutor ───────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
AI_SYSTEM_CONTEXT = (
    "You are an academic tutor for an EEE undergraduate at University of Asia "
    "Pacific, Bangladesh. Answer precisely and concretely. When you use the "
    "student's own notes, label that content '[From Notes]'. When you add "
    "external knowledge, label it '[Added Knowledge]'. Be concise but complete."
)

# ── Deadline prep blocks ───────────────────────────────────────────────────
PREP_DAYS_BEFORE = 3        # schedule prep this many days before a deadline
PREP_HOUR = 18              # prep block starts at this hour (local)
PREP_DURATION_HOURS = 2     # prep block length

# ── App ────────────────────────────────────────────────────────────────────
APP_TITLE = "EEE Academic OS"
APP_SUBTITLE = "Hybrid AI + Performance + Deadlines"
COURSE_OPTIONS = [
    "Circuit Theory",
    "Electronics I",
    "Digital Logic Design",
    "Signals & Systems",
    "Electromagnetic Fields",
    "Control Systems",
    "Power Systems",
    "Microprocessors",
    "Machine Learning",
    "Robotics",
    "Other",
]
