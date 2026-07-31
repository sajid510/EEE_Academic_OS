"""Deterministic sample data for demo mode (no Google account needed).

Used by the app when secrets are not configured, and by tests. Seeded so the
generated analytics are stable.
"""

import numpy as np
import pandas as pd

from src.analytics import DATE_COL, COURSE_COL, TOPIC_COL, SCORE_COL, TIME_COL, NOTES_COL

SAMPLE_COURSES = {
    "Circuit Theory": ["Thevenin/Norton", "Transient Analysis", "AC Power"],
    "Electronics I": ["Diode Circuits", "BJT Amplifiers", "Op-Amps"],
    "Digital Logic Design": ["K-Maps", "Flip-Flops", "FSM Design"],
    "Signals & Systems": ["Fourier Transform", "Convolution", "Z-Transform"],
    "Machine Learning": ["Linear Regression", "Neural Networks", "Feature Engineering"],
}


def sample_performance(seed=42, rows=36):
    """Build a realistic, seeded Performance_Log DataFrame."""
    rng = np.random.default_rng(seed)
    records = []

    pairs = [(c, t) for c, topics in SAMPLE_COURSES.items() for t in topics]
    dates = pd.date_range(end=pd.Timestamp.now().normalize(), periods=rows, freq="2D")

    for i in range(rows):
        course, topic = pairs[i % len(pairs)]
        base = 55 + (i * 7) % 35  # gentle upward drift
        records.append({
            DATE_COL: dates[i].date(),
            COURSE_COL: course,
            TOPIC_COL: topic,
            SCORE_COL: int(max(30, min(100, base + int(rng.integers(-12, 12))))),
            TIME_COL: round(float(rng.uniform(0.5, 4.0)), 1),
            NOTES_COL: "",
        })

    return pd.DataFrame(records)


def has_demo_columns(df):
    """True when the frame has the expected performance columns."""
    return df is not None and not df.empty and SCORE_COL in df.columns
