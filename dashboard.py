"""Compatibility entry point — same as ``streamlit run app.py``.

Kept so the original command ``streamlit run dashboard.py`` still works.
"""

import app  # noqa: F401  (top-level Streamlit code runs on import)
