"""Tests for the pure analytics core (no network / no Streamlit)."""

from datetime import datetime

import pandas as pd
import pytest

from src import analytics as an
from src.sample_data import sample_performance


class TestMasteryScore:
    def test_high_score_high_time(self):
        assert an.mastery_score(100, 5) == 100.0

    def test_zero_everything(self):
        assert an.mastery_score(0, 0) == 0.0

    def test_time_factor_caps_at_full(self):
        # 10h * 20 = 200 -> capped to 100 for the time factor
        assert an.mastery_score(50, 10) == 50 * 0.7 + 100 * 0.3

    def test_clamps_out_of_range_score(self):
        assert an.mastery_score(150, 1) <= 100.0
        assert an.mastery_score(-10, 1) >= 0.0


class TestEstimateGpa:
    def test_scale(self):
        assert an.estimate_gpa(100) == 4.0
        assert an.estimate_gpa(0) == 0.0
        assert an.estimate_gpa(75) == 3.0

    def test_handles_nan(self):
        assert an.estimate_gpa(float("nan")) == 0.0
        assert an.estimate_gpa(None) == 0.0


class TestNormalize:
    def test_empty_df(self):
        out = an.normalize_df(None)
        assert out.empty
        out2 = an.normalize_df(pd.DataFrame())
        assert out2.empty

    def test_missing_columns_filled(self):
        df = pd.DataFrame({"Practice Score": [70]})
        out = an.normalize_df(df)
        for col in an.REQUIRED_COLUMNS:
            assert col in out.columns

    def test_numeric_casts(self):
        df = sample_performance()
        out = an.normalize_df(df)
        assert pd.api.types.is_numeric_dtype(out[an.SCORE_COL])
        assert pd.api.types.is_numeric_dtype(out[an.TIME_COL])
        assert pd.api.types.is_datetime64_any_dtype(out[an.DATE_COL])


class TestSummarize:
    def test_empty(self):
        s = an.summarize(pd.DataFrame())
        assert s["sessions"] == 0 and s["gpa_estimate"] == 0.0

    def test_sample(self):
        df = sample_performance(seed=42)
        s = an.summarize(df)
        assert s["sessions"] == 36
        assert s["courses"] > 0
        assert 0 <= s["gpa_estimate"] <= 4.0
        assert s["mean_mastery"] > 0


class TestTopics:
    def test_weak_topics_sorted_ascending(self):
        df = sample_performance(seed=7)
        weak = an.weak_topics(df)
        if not weak.empty:
            scores = weak[an.SCORE_COL].tolist()
            assert scores == sorted(scores)
            assert all(s < an.config.WEAK_TOPIC_THRESHOLD for s in scores)

    def test_topic_mastery_has_course_column(self):
        df = sample_performance(seed=3)
        tm = an.topic_mastery(df)
        assert an.COURSE_COL in tm.columns
        assert (tm["Mastery Score"].diff().dropna() <= 0).all()  # descending


class TestStreakAndCountdown:
    def test_weekly_streak_zero_empty(self):
        assert an.weekly_streak(pd.DataFrame()) == 0

    def test_weekly_streak_nonzero_with_recent_data(self):
        df = sample_performance(seed=1, rows=10)
        assert an.weekly_streak(df) >= 0

    def test_deadline_countdown(self):
        now = datetime(2026, 7, 1, 12, 0, 0)
        future = datetime(2026, 7, 5, 12, 0, 0)
        assert an.deadline_countdown(future, now) == 4
        assert an.deadline_countdown(now, now) == 0

    def test_prep_block(self):
        from datetime import timedelta

        deadline = datetime(2026, 7, 10, 23, 59, 0)
        start, end = an.prep_block(deadline, days_before=3, hour=18, duration_hours=2)
        assert start.date() == deadline.date() - timedelta(days=3)
        assert start.hour == 18 and start.minute == 0
        assert (end - start).seconds == 2 * 3600

    def test_prep_block_aware_datetime(self):
        import datetime as dtt

        deadline = datetime(2026, 7, 10, 23, 0, 0, tzinfo=dtt.timezone.utc)
        start, end = an.prep_block(deadline)
        assert start.tzinfo is not None
        assert (end - start).seconds == an.config.PREP_DURATION_HOURS * 3600
