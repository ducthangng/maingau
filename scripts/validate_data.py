"""Validate a (new) workbook against kg/data_contract.yaml before building (Agent KG, README §6.15).

Exit code 1 if there is any ERROR, so it can gate a pipeline:
  .venv/bin/python scripts/validate_data.py [--workbook data/maingau_nba_mockdata.xlsx] && python -m nba.build ...
Writes out/data_validation.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.data import DEFAULT_WORKBOOK  # noqa: E402
from nba.kg.intake import CONFIG_PATH, CONTRACT_PATH, validate_workbook  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    ap.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    ap.add_argument("--config", type=Path, default=CONFIG_PATH, help="config/kg.yaml whose eval_time the pipeline uses")
    ap.add_argument("--out", type=Path, default=REPO / "out" / "data_validation.md")
    args = ap.parse_args()
    issues = validate_workbook(args.workbook, args.contract, args.config)
    errors = [i for i in issues if i.level == "ERROR"]
    warnings = [i for i in issues if i.level == "WARNING"]
    lines = [f"# Data validation: {args.workbook.name}", "",
             f"Contract `{args.contract.relative_to(REPO) if args.contract.is_relative_to(REPO) else args.contract}`: "
             f"**{len(errors)} errors, {len(warnings)} warnings.** Errors stop the pipeline.", "",
             "| Level | Check | Where | Detail | Count | Examples |", "|---|---|---|---|---:|---|"]
    for i in errors + warnings:
        lines.append(f"| {i.level} | {i.code} | `{i.where}` | {i.detail} | {i.count} | {', '.join(i.examples)} |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for i in errors + warnings:
        print(f"{i.level:7s} {i.code:20s} {i.where:45s} {i.detail[:90]}")
    print(f"\n{len(errors)} errors, {len(warnings)} warnings -> {args.out.relative_to(REPO) if args.out.is_relative_to(REPO) else args.out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
