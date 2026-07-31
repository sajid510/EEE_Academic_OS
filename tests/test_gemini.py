"""Tests for the AI tutor prompt builder and error handling."""

from src import gemini


class TestBuildPrompt:
    def test_includes_question_and_notes(self):
        prompt = gemini.build_prompt("What is Thevenin?", "Rth = Voc/Isc")
        assert "What is Thevenin?" in prompt["user"]
        assert "Rth = Voc/Isc" in prompt["user"]
        assert "[From Notes]" in prompt["user"]

    def test_no_notes_placeholder(self):
        prompt = gemini.build_prompt("Q?", "")
        assert "(no notes provided)" in prompt["user"]

    def test_history_rendered(self):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        prompt = gemini.build_prompt("next?", "notes", history=history)
        assert "Student: hello" in prompt["user"]
        assert "Tutor: hi there" in prompt["user"]


class TestAskGemini:
    def test_missing_key_returns_warning(self):
        answer = gemini.ask_gemini("q", "notes", api_key="")
        assert "not configured" in answer
