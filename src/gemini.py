"""AI Tutor — Gemini-backed study assistant.

Pure functions for prompt building are separated from the network call so they
can be unit-tested without an API key.
"""

import requests

from src import config


def build_prompt(question, notes, history=None):
    """Build the tutor prompt from the question, personal notes and history.

    Returns a dict of ``{"system": str, "user": str}``.
    """
    notes_block = (notes or "").strip()
    if not notes_block:
        notes_block = "(no notes provided)"

    history_block = ""
    if history:
        rendered = []
        for turn in history[-6:]:
            role = "Student" if turn.get("role") == "user" else "Tutor"
            rendered.append(f"{role}: {turn.get('content', '')}")
        history_block = "\n".join(rendered) + "\n"

    system = config.AI_SYSTEM_CONTEXT

    user = (
        "RECENT CONVERSATION:\n"
        f"{history_block}\n"
        "NOTES:\n"
        f"{notes_block}\n\n"
        "QUESTION:\n"
        f"{question}\n\n"
        "Instructions:\n"
        "1. Prioritize the notes content.\n"
        "2. If the notes do not contain enough information, use general "
        "knowledge.\n"
        "3. Clearly label content sections as [From Notes] and [Added "
        "Knowledge].\n"
        "4. Be structured and concise.\n"
    )
    return {"system": system, "user": user}


def ask_gemini(question, notes, api_key, model=None, history=None, timeout=60):
    """Call the Gemini generateContent endpoint and return the answer text.

    Returns a string on success or a user-friendly error string on failure.
    """
    model = model or config.GEMINI_MODEL
    if not api_key:
        return "⚠️ Gemini API key is not configured."

    prompt = build_prompt(question, notes, history=history)
    url = config.GEMINI_ENDPOINT.format(model=model)

    payload = {
        "system_instruction": {"parts": [{"text": prompt["system"]}]},
        "contents": [{"parts": [{"text": prompt["user"]}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
            "topP": 0.9,
        },
    }

    try:
        response = requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return "⚠️ Gemini returned an empty response."
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or "⚠️ Gemini returned an empty response."

    except requests.exceptions.Timeout:
        return "⚠️ Gemini timed out. Try again."
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        return f"⚠️ Gemini HTTP error {status}. Check your API key and quota."
    except requests.exceptions.RequestException as exc:
        return f"⚠️ Network error contacting Gemini: {exc}"
