"""Databricks App entry point: the NBA API and the built dashboard on one port (scripts/databricks_deploy.py app).

Runs in the App's own container as its service principal. The engine reads maingau_raw through the SQL warehouse
attached to the App (MAINGAU_DATABRICKS_WAREHOUSE), approvals and service reactions go to maingau_nba.decision_log /
service_feedback, and the dashboard (web/dist) talks to the API on the same origin.
"""

from __future__ import annotations

import mimetypes
import os
import sys
import threading
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("MAINGAU_DATA_SOURCE", "databricks")
os.environ.setdefault("MAINGAU_LLM", "none")

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.app import app  # noqa: E402

DIST = REPO / "web" / "dist"
# Browsers only run module scripts served as JavaScript; some systems map .js to text/plain.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
PORT = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))

app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def dashboard(path: str):
    """Static files of the built dashboard; any other path is a page of the single-page app."""
    if path.startswith("api/"):
        raise HTTPException(404, "Unknown API path")
    target = (DIST / path).resolve()
    if path and target.is_file() and DIST.resolve() in target.parents:
        return FileResponse(target)
    return FileResponse(DIST / "index.html")


def warm_up() -> None:
    """Load the 750 customers once at start, so the first visitor does not wait for it."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/summary", timeout=600).read()
    except OSError as exc:
        print(f"warm-up failed: {exc}", flush=True)


if __name__ == "__main__":
    import uvicorn

    threading.Timer(2.0, warm_up).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
