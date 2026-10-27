"""The nightly NBA run as a Databricks Job (deployed by scripts/databricks_deploy.py; docs/databricks.md).

  --step validate   check the raw layer against kg/data_contract.yaml; an ERROR fails the run
  --step decide     feedback from Delta -> customer memory -> decide for every customer -> publish to maingau_nba

Runs on Databricks serverless compute. SQL goes through the job's own Spark session (nba.lakehouse.SparkWarehouse),
so Unity Catalog lineage shows this job reading maingau_raw and writing maingau_nba. There are no local files here:
if the raw layer cannot be read, the run fails instead of falling back.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# A Databricks python task exec()s this file without __file__: the deploy script passes the code folder as --repo.
REPO = Path(sys.argv[sys.argv.index("--repo") + 1]) if "--repo" in sys.argv else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ["MAINGAU_DATA_SOURCE"] = "databricks"
os.environ.setdefault("MAINGAU_LLM", "none")  # deterministic: the job never calls an AI backend


def connected():
    from nba import lakehouse

    st = lakehouse.status()
    if st["source"] != "databricks":
        raise SystemExit(f"The raw layer could not be read: {st['detail']}")
    print(f"Data: {st['detail']}")
    return lakehouse, *lakehouse.connection()


def validate() -> None:
    connected()
    from nba.kg.intake import validate_workbook

    issues = validate_workbook()
    errors = [i for i in issues if i.level == "ERROR"]
    for i in issues:
        print(f"{i.level:7s} {i.code:20s} {i.where:45s} {i.detail[:90]}")
    print(f"Data contract: {len(errors)} errors, {len(issues) - len(errors)} warnings")
    if errors:
        raise SystemExit(1)


def decide() -> None:
    lakehouse, wh, s = connected()
    out = Path(tempfile.mkdtemp(prefix="nba-run-"))
    decisions, service = lakehouse.read_records(wh, s)
    for name, rows in (("decision_log.jsonl", decisions), ("service_feedback.jsonl", service)):
        (out / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"Feedback from Databricks: {len(decisions)} decisions, {len(service)} service reactions")

    from nba import build

    start = time.perf_counter()
    build.main(["--out", str(out), "--learn", "--memory", str(out / "customer_memory.jsonl"),
                "--no-report", "--skip-validation"])  # validated by the previous task
    print(f"Decided in {time.perf_counter() - start:.1f}s")
    counts = lakehouse.publish(wh, s, out)
    print(f"Published to {s.catalog}.{s.out_schema}: " + ", ".join(f"{t} {n}" for t, n in counts.items()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", choices=("validate", "decide"), required=True)
    ap.add_argument("--repo", help="folder holding nba/, kg/, config/ (set by the job)")
    args = ap.parse_args()
    {"validate": validate, "decide": decide}[args.step]()


if __name__ == "__main__":
    main()
