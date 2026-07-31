"""Self-learning memory for the EEE Academic OS AI tutor.

The tutor gets better with every session by persisting what it learns about
the user into a local ``memory/memory.json`` (git-ignored) that can also be
exported/imported as a free backup.

What the memory learns:

- **Preferences** — explanation style (concise/detailed), difficulty, focus
  areas the user cares about.
- **Interactions** — every question + answer + rating (👍/👎) + course/topic,
  so the tutor can see what kind of answers the user accepts.
- **Corrections** — user feedback like *"explain with a diagram"* or *"too
  much theory"*, turned into DO/AVOID rules injected into future prompts.
- **Stats** — session counts, average ratings, and a simple per-topic
  engagement score.

Before every answer the app calls :meth:`personalization_context` and merges
the result into the Gemini system prompt — that is what makes outputs
increasingly customized and better over time.
"""

import json
import re
from datetime import datetime
from pathlib import Path

DEFAULT_MEMORY_FILE = "memory/memory.json"
MAX_INTERACTIONS = 300
MAX_CORRECTIONS = 40

STYLE_OPTIONS = ["concise", "balanced", "detailed"]
DIFFICULTY_OPTIONS = ["gentle", "balanced", "advanced"]
FOCUS_OPTIONS = ["weak topics", "exam prep", "deep understanding", "quick review"]


def _now():
    return datetime.now().isoformat(timespec="seconds")


class TutorMemory:
    """Persistent JSON-backed learning memory for the AI tutor."""

    def __init__(self, path=DEFAULT_MEMORY_FILE):
        self.path = Path(path)
        self.data = {
            "version": 1,
            "preferences": {
                "style": "balanced",
                "difficulty": "balanced",
                "focus": "weak topics",
                "courses": [],
            },
            "interactions": [],
            "corrections": [],
            "stats": {"sessions": 0, "ratings": 0, "avg_rating": 0.0},
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.load()

    # ── persistence ─────────────────────────────────────────────────────────
    def load(self):
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    merged = self.data
                    merged.update({k: v for k, v in stored.items() if k in merged})
                    merged["preferences"] = {
                        **self.data["preferences"],
                        **{k: v for k, v in (stored.get("preferences") or {}).items()
                           if k in self.data["preferences"]},
                    }
                    merged["interactions"] = list(stored.get("interactions") or [])
                    merged["corrections"] = list(stored.get("corrections") or [])
                    self.data = merged
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[learning] Could not load memory ({exc}) — starting fresh")
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = _now()
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self

    def export_json(self):
        return json.dumps(self.data, ensure_ascii=False, indent=2)

    def import_json(self, raw):
        stored = json.loads(raw)
        if not isinstance(stored, dict):
            raise ValueError("Invalid memory file")
        self.data = stored
        self.save()

    # ── preferences ─────────────────────────────────────────────────────────
    def set_preference(self, key, value):
        if key in self.data["preferences"]:
            self.data["preferences"][key] = value

    def record_course(self, course):
        """Track recently studied courses, most recent first."""
        prefs = self.data["preferences"]
        courses = list(prefs["courses"])
        if course:
            if course in courses:
                courses.remove(course)
            courses.insert(0, course)
            prefs["courses"] = courses[:20]

    # ── interactions / feedback ─────────────────────────────────────────────
    def record_interaction(self, question, answer, course="", topic="",
                           rating=None, correction=""):
        """Log a tutor exchange with optional rating and correction."""
        self.data["interactions"].append({
            "ts": _now(),
            "question": str(question or "")[:500],
            "answer": str(answer or "")[:2000],
            "course": str(course or ""),
            "topic": str(topic or ""),
            "rating": rating,          # None | 1 (good) | -1 (needs work)
            "correction": str(correction or "")[:500],
        })
        self.data["interactions"] = self.data["interactions"][-MAX_INTERACTIONS:]

        if rating is not None:
            self.data["stats"]["ratings"] += 1
        if correction:
            self.data["corrections"].append({
                "ts": _now(),
                "rule": str(correction or "")[:300],
                "course": str(course or ""),
            })
            self.data["corrections"] = self.data["corrections"][-MAX_CORRECTIONS:]

        self.data["stats"]["sessions"] += 1
        self._update_avg_rating()
        self.save()
        return self.data["stats"]["sessions"]

    def _update_avg_rating(self):
        rated = [i for i in self.data["interactions"] if i.get("rating") is not None]
        if rated:
            self.data["stats"]["avg_rating"] = round(
                sum(1 for i in rated if i["rating"] == 1) / len(rated), 2
            )

    # ── personalization context for prompts ─────────────────────────────────
    def corrections_as_rules(self, top_n=3):
        rules = []
        for c in self.data["corrections"][-top_n:]:
            text = str(c.get("rule") or "").strip()
            if text:
                rules.append(text)
        return rules

    def preferred_courses(self, top_n=3):
        return self.data["preferences"]["courses"][-top_n:]

    def personalization_context(self, weak_topics=None, courses=None):
        """Build a prompt block describing the user's learned preferences."""
        prefs = self.data["preferences"]
        parts = []

        style = prefs.get("style") or "balanced"
        diff = prefs.get("difficulty") or "balanced"
        focus = prefs.get("focus") or "weak topics"
        parts.append(
            f"Style: {style}. Difficulty: {diff}. Primary focus: {focus}."
        )

        if courses:
            parts.append("Courses being studied: " + ", ".join(courses[:5]) + ".")

        weak = list(weak_topics or [])[:5]
        if weak:
            parts.append(
                "The student is weakest in these topics — prioritize explaining "
                "them clearly: " + ", ".join(str(w) for w in weak) + "."
            )

        rules = self.corrections_as_rules(3)
        if rules:
            parts.append("Learned DO/AVOID rules from past feedback: " + " ".join(
                f"«{r}»" for r in rules))

        if self.data["stats"]["avg_rating"] > 0.6 and self.data["stats"]["ratings"] >= 3:
            parts.append(
                "The student rates your recent answers highly — keep the "
                "current style."
            )

        if not parts:
            parts.append("No learned preferences yet — default tutoring style.")
        return " ".join(parts)

    def stats(self):
        return {
            "sessions": self.data["stats"]["sessions"],
            "ratings": self.data["stats"]["ratings"],
            "avg_rating": self.data["stats"]["avg_rating"],
            "interactions": len(self.data["interactions"]),
            "corrections": len(self.data["corrections"]),
            "preferences": dict(self.data["preferences"]),
        }
