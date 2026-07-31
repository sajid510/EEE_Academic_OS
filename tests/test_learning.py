"""Tests for the AI tutor self-learning memory."""

from src.learning import TutorMemory


class TestPreferences:
    def test_defaults(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        assert mem.data["preferences"]["style"] == "balanced"
        assert mem.stats()["sessions"] == 0

    def test_set_preference(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.set_preference("style", "detailed")
        assert mem.data["preferences"]["style"] == "detailed"

    def test_record_course_keeps_recent_first(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.record_course("Robotics")
        mem.record_course("Signals & Systems")
        mem.record_course("Robotics")
        assert mem.preferred_courses(2) == ["Robotics", "Signals & Systems"]


class TestInteractions:
    def test_record_interaction_increments_sessions(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.record_interaction("q", "a", course="Robotics", rating=1)
        assert mem.stats()["sessions"] == 1
        assert mem.stats()["ratings"] == 1
        assert mem.stats()["avg_rating"] == 1.0

    def test_correction_adds_rule(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.record_interaction("q", "a", correction="use a diagram")
        assert mem.data["corrections"][-1]["rule"] == "use a diagram"

    def test_persists_across_reload(self, tmp_path):
        path = str(tmp_path / "mem.json")
        mem = TutorMemory(path=path)
        mem.record_interaction("q", "a", rating=-1, correction="too long")
        mem.set_preference("style", "concise")
        mem.save()

        reloaded = TutorMemory(path=path)
        assert reloaded.stats()["sessions"] == 1
        assert reloaded.stats()["avg_rating"] == 0.0
        assert reloaded.data["preferences"]["style"] == "concise"
        assert len(reloaded.corrections_as_rules(3)) == 1


class TestPersonalization:
    def test_context_includes_style(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        ctx = mem.personalization_context()
        assert "balanced" in ctx

    def test_context_includes_weak_topics(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        ctx = mem.personalization_context(weak_topics=["Thevenin", "Z-Transform"])
        assert "Thevenin" in ctx

    def test_context_includes_learned_rules(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.record_interaction("q", "a", correction="always show units")
        ctx = mem.personalization_context()
        assert "always show units" in ctx

    def test_context_includes_courses(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.record_course("Robotics")
        ctx = mem.personalization_context(courses=mem.preferred_courses(3))
        assert "Robotics" in ctx


class TestExportImport:
    def test_roundtrip(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        mem.record_interaction("q", "a", rating=1)
        raw = mem.export_json()

        mem2 = TutorMemory(path=str(tmp_path / "other.json"))
        mem2.import_json(raw)
        assert mem2.stats()["sessions"] == 1
        assert mem2.stats()["avg_rating"] == 1.0

    def test_import_invalid(self, tmp_path):
        mem = TutorMemory(path=str(tmp_path / "mem.json"))
        try:
            mem.import_json("{not json")
            assert False, "should raise"
        except Exception:
            assert True
