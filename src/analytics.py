"""Pure study-analytics logic.

These functions never touch the network or Streamlit, which keeps the core of
the EEE Academic OS unit-testable and reusable.
"""

from datetime import date, datetime, timedelta

import pandas as pd

from src import config

# Expected column names in the Performance_Log sheet.
DATE_COL = "Date"
COURSE_COL = "Course"
TOPIC_COL = "Topic"
SCORE_COL = "Practice Score"
TIME_COL = "Time Spent"
NOTES_COL = "Notes"

REQUIRED_COLUMNS = [DATE_COL, COURSE_COL, TOPIC_COL, SCORE_COL, TIME_COL]


def clamp(value, low=0.0, high=config.MAX_SCORE):
    """Clamp a numeric value into [low, high]."""
    return max(low, min(high, float(value)))


def time_factor(hours):
    """Convert study hours into a 0-100 factor (capped at 100)."""
    hours = max(0.0, float(hours or 0))
    return clamp(hours * config.TIME_FACTOR_PER_HOUR, high=100.0)


def mastery_score(practice_score, time_hours):
    """Blend practice score and study time into a 0-100 mastery score."""
    score = clamp(practice_score)
    return round(score * config.SCORE_WEIGHT + time_factor(time_hours) * config.TIME_WEIGHT, 1)


def estimate_gpa(mean_score):
    """Map a mean practice score (0-100) to a 0-4.0 GPA estimate."""
    mean = 0.0 if mean_score is None or pd.isna(mean_score) else float(mean_score)
    return round(clamp(mean / config.MAX_SCORE * config.GPA_SCALE, high=config.GPA_SCALE), 2)


def normalize_df(df):
    """Normalize a raw sheet DataFrame: numeric casts + parsed dates.

    Returns a copy with ONLY the known columns; missing columns are filled so
    downstream analytics never KeyError on a new/empty sheet.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    out = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in out.columns:
            out[col] = None

    out[SCORE_COL] = pd.to_numeric(out[SCORE_COL], errors="coerce")
    out[TIME_COL] = pd.to_numeric(out[TIME_COL], errors="coerce")
    out[DATE_COL] = pd.to_datetime(out[DATE_COL], errors="coerce")
    out[COURSE_COL] = out[COURSE_COL].fillna("Unknown").astype(str)
    out[TOPIC_COL] = out[TOPIC_COL].fillna(out[COURSE_COL]).astype(str)

    out = out.dropna(subset=[SCORE_COL])
    return out.reset_index(drop=True)


def add_mastery(df):
    """Return a copy of the normalized frame with a Mastery Score column."""
    out = normalize_df(df)
    if out.empty:
        out["Mastery Score"] = pd.Series(dtype=float)
        return out
    out["Mastery Score"] = out.apply(
        lambda r: mastery_score(r[SCORE_COL], r[TIME_COL]), axis=1
    )
    return out


def weak_topics(df, threshold=config.WEAK_TOPIC_THRESHOLD):
    """DataFrame of topics whose average practice score is below threshold."""
    out = add_mastery(df)
    if out.empty:
        return out
    avg = (
        out.groupby([COURSE_COL, TOPIC_COL])[SCORE_COL]
        .mean()
        .reset_index()
        .sort_values(SCORE_COL, ascending=True)
    )
    return avg[avg[SCORE_COL] < threshold].reset_index(drop=True)


def strong_topics(df, threshold=config.WEAK_TOPIC_THRESHOLD):
    """DataFrame of topics at or above the threshold, best first."""
    out = add_mastery(df)
    if out.empty:
        return out
    avg = (
        out.groupby([COURSE_COL, TOPIC_COL])[SCORE_COL]
        .mean()
        .reset_index()
        .sort_values(SCORE_COL, ascending=False)
    )
    return avg[avg[SCORE_COL] >= threshold].reset_index(drop=True)


def topic_mastery(df):
    """Per-course average mastery (0-100), best first."""
    out = add_mastery(df)
    if out.empty:
        return out
    return (
        out.groupby(COURSE_COL)["Mastery Score"]
        .mean()
        .reset_index()
        .sort_values("Mastery Score", ascending=False)
        .reset_index(drop=True)
    )


def trend_series(df):
    """Daily mean practice score for time-series charts."""
    out = add_mastery(df)
    if out.empty:
        return out
    ts = out.dropna(subset=[DATE_COL]).set_index(DATE_COL)
    return ts[SCORE_COL].resample("D").mean().dropna().reset_index()


def weekly_streak(df):
    """Number of consecutive calendar weeks (ending now) with >=1 session."""
    out = normalize_df(df)
    if out.empty:
        return 0
    weeks = out.dropna(subset=[DATE_COL])[DATE_COL].dt.to_period("W").unique()
    if len(weeks) == 0:
        return 0
    current = pd.Timestamp.now().to_period("W")
    week_set = set(weeks)
    streak = 0
    probe = current
    while probe in week_set:
        streak += 1
        probe = probe - 1
    return streak


def deadline_countdown(event_dt, now=None):
    """Whole days from now until an event (negative = already past)."""
    now = now or datetime.now()
    if event_dt.tzinfo is not None and now.tzinfo is None:
        event_dt = event_dt.replace(tzinfo=None)
    return (event_dt - now).days


def prep_block(event_dt, days_before=config.PREP_DAYS_BEFORE,
               hour=config.PREP_HOUR, duration_hours=config.PREP_DURATION_HOURS):
    """Compute a prep-block (start, end) datetime before a deadline.

    Returns naive datetimes in the same tz as ``event_dt`` (or local if naive).
    """
    if event_dt.tzinfo is not None:
        start = event_dt.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_before)
    else:
        start = datetime(event_dt.year, event_dt.month, event_dt.day, hour, 0) - timedelta(days=days_before)
    return start, start + timedelta(hours=duration_hours)


def summarize(df):
    """One-row summary dict used for metrics cards."""
    out = add_mastery(df)
    if out.empty:
        return {
            "sessions": 0,
            "courses": 0,
            "mean_score": 0.0,
            "mean_mastery": 0.0,
            "gpa_estimate": 0.0,
            "weak_topics": 0,
            "streak": 0,
        }
    return {
        "sessions": int(len(out)),
        "courses": int(out[COURSE_COL].nunique()),
        "mean_score": round(float(out[SCORE_COL].mean()), 1),
        "mean_mastery": round(float(out["Mastery Score"].mean()), 1),
        "gpa_estimate": estimate_gpa(float(out[SCORE_COL].mean())),
        "weak_topics": int(len(weak_topics(out))),
        "streak": weekly_streak(out),
    }
