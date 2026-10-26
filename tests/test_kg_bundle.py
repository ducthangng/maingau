"""KG bundle and preview export (README §5.6)."""

import json
import subprocess
import sys
from pathlib import Path

from nba.contracts import IndexRow, Summary
from nba.kg.bundle import kg_bundle, source_info

REPO = Path(__file__).resolve().parents[1]


def test_bundle_matches_individual_calls(states, policy, pop, kg_all):
    b = kg_bundle(states["MG-100068"], policy, pop)
    sig, cands, blocked, tri = kg_all["MG-100068"]
    assert b.signals == sig and b.candidates == cands and b.blocked == blocked and b.triage == tri
    assert len(b.consent) == 6 and any(c.channel == "service_agent" for c in b.channels)


def test_source_info_covers_sources_sheet(tables):
    info = source_info(tables)
    assert len(info) == 18 and info["charge_sessions"].latency


def test_preview_export_validates(tmp_path):
    subprocess.run([sys.executable, str(REPO / "scripts" / "export_preview.py"), "--out", str(tmp_path),
                    "--customers", "MG-100068,MG-100009,MG-100112"], check=True, cwd=REPO)
    rows = [IndexRow(**r) for r in json.loads((tmp_path / "index.json").read_text())]
    assert [r.customer_id for r in rows] == ["MG-100009", "MG-100068", "MG-100112"]  # P1, P2, P4
    Summary(**json.loads((tmp_path / "summary.json").read_text()))
    assert (tmp_path / "kg" / "MG-100068.json").exists()
