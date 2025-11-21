"""Streamlit entrypoint to run the SNIC-SAT app from the repo root.

This wrapper keeps backward compatibility for deployments that expect
`app.py` at the repository root by delegating execution to
`SNIC-SAT/app.py` while ensuring local imports still resolve.
"""
from __future__ import annotations

import os
import runpy
import sys

APP_DIR = os.path.join(os.path.dirname(__file__), "SNIC-SAT")
TARGET_APP = os.path.join(APP_DIR, "app.py")

# Make sure modules inside SNIC-SAT are importable when the app is
# executed from the repository root (e.g., `streamlit run app.py`).
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

runpy.run_path(TARGET_APP, run_name="__main__")
