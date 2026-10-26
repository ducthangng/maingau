"""Write JSON Schemas for the shared contracts to docs/schema/ (Agent KG).

Agent CARDS generates TypeScript types from these files, e.g. with json-schema-to-typescript.
Run: .venv/bin/python scripts/export_schema.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.contracts import CustomerCard, DecisionRequest, IndexRow, Summary  # noqa: E402

OUT = REPO / "docs" / "schema"
MODELS = {
    "customer_card": CustomerCard,
    "index_row": IndexRow,
    "summary": Summary,
    "decision_request": DecisionRequest,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        path = OUT / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
