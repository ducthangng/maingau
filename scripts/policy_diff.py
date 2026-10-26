"""Which customers would get a different decision under a changed policy? (Agent KG, README §6.15)

Compares a base policy (default: kg/policy.yaml + config/kg.yaml at git HEAD) with a candidate policy
(default: the files in the working tree) on every customer, using Agent NBA's engine (read-only) to
decide. Lists only the customers whose chosen action changes: customer, before, after.

  .venv/bin/python scripts/policy_diff.py                       # working tree vs HEAD
  .venv/bin/python scripts/policy_diff.py --base origin/main     # working tree vs another ref
  .venv/bin/python scripts/policy_diff.py --policy my_policy.yaml --config my_kg.yaml

Writes out/policy_diff.md and out/policy_diff.json. Only the policy files are swapped; code is the same.
Exit code 2 if a policy cannot be loaded (the previous outputs are removed so nothing stale remains).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest import mock

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba.data import load_workbook  # noqa: E402
from nba.engine.assemble import assemble  # noqa: E402  (Agent NBA, read-only use)
from nba.engine.config import load_config  # noqa: E402
from nba.kg.policy import CONFIG_PATH, POLICY_PATH, PolicyError, load_policy  # noqa: E402
from nba.state import build_states, population  # noqa: E402

OUT_MD, OUT_JSON = REPO / "out" / "policy_diff.md", REPO / "out" / "policy_diff.json"


def _policy_in_use(policy):
    """Make modules that cache the working-tree policy (Agent CARDS' tone inference) use `policy` for this run.

    Runtime override only; no file outside Agent KG's paths is changed.
    """
    try:
        import nba.profile.tone  # noqa: F401
    except ImportError:
        return contextlib.nullcontext()
    return mock.patch("nba.profile.tone.policy", lambda: policy)


def decisions(policy, tables, p_mode=None, customer_ids=None) -> dict[str, str]:
    """customer_id -> chosen tuple_id (or NO_ACTION) under `policy`, as Agent NBA's Runtime.load would decide."""
    t = datetime.fromisoformat(policy.config["eval_time"])
    states = build_states(tables, t, snapshot_mode=policy.config["snapshot_mode"], customer_ids=customer_ids)
    cfg = load_config(tables, p_mode=p_mode)
    cfg.history = [r for r in cfg.history if r.get("decided_at") and r["decided_at"] <= t]
    pop = population(tables)
    with _policy_in_use(policy):
        return {cid: assemble(s, pop, policy, cfg).chosen.tuple_id for cid, s in sorted(states.items())}


def diff_decisions(base, candidate, tables, p_mode=None, customer_ids=None) -> list[tuple[str, str, str]]:
    before = decisions(base, tables, p_mode, customer_ids)
    after = decisions(candidate, tables, p_mode, customer_ids)
    return [(cid, before[cid], after[cid]) for cid in sorted(before) if before[cid] != after.get(cid)]


class DiffError(Exception):
    pass


def _from_git(ref: str, rel: str, tmp: Path) -> Path:
    proc = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{rel}"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise DiffError(f"cannot read {rel} at {ref}: {proc.stderr.strip()}")
    path = tmp / rel.replace("/", "_")
    path.write_text(proc.stdout, encoding="utf-8")
    return path


FILLED_BLOCKS = ("parameters", "compliance")  # policy blocks added after older commits


def _fill_missing_parameters(base_path: Path, candidate_path: Path, tmp: Path) -> tuple[Path, str | None]:
    """A base that predates a block (`parameters`, `compliance`) gets the candidate's copy, so only rule
    changes are compared."""
    base_raw = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    missing = [b for b in FILLED_BLOCKS if b not in base_raw]
    if not missing:
        return base_path, None
    cand_raw = yaml.safe_load(candidate_path.read_text(encoding="utf-8")) or {}
    for block in missing:
        base_raw[block] = cand_raw.get(block) or {}
    filled = tmp / "base_policy_filled.yaml"
    filled.write_text(yaml.safe_dump(base_raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    names = " and ".join(f"`{b}`" for b in missing)
    return filled, f"the base policy has no {names} block (it predates them); the candidate's copy was used for it"


def _md(tuple_id: str) -> str:
    return "`" + tuple_id.replace("|", "\\|") + "`"  # '|' would split the Markdown table cell


def _rel(p: Path) -> str:
    p = Path(p)
    return str(p.relative_to(REPO)) if p.is_absolute() and p.is_relative_to(REPO) else str(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="HEAD", help="git ref for the base policy files (default HEAD)")
    ap.add_argument("--base-policy", type=Path, help="base kg/policy.yaml path instead of --base")
    ap.add_argument("--base-config", type=Path, help="base config/kg.yaml path instead of --base")
    ap.add_argument("--policy", type=Path, default=POLICY_PATH, help="candidate policy (default: working tree)")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH, help="candidate config (default: working tree)")
    ap.add_argument("--p-mode", choices=("rate", "uplift"))
    ap.add_argument("--customers", default="")
    args = ap.parse_args()

    start = time.perf_counter()
    for f in (OUT_MD, OUT_JSON):
        f.unlink(missing_ok=True)  # never leave a stale result behind
    tables = load_workbook()
    notes: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            base_policy = args.base_policy or _from_git(args.base, "kg/policy.yaml", tmp)
            base_config = args.base_config or _from_git(args.base, "config/kg.yaml", tmp)
            base_policy, note = _fill_missing_parameters(Path(base_policy), args.policy, tmp)
            if note:
                notes.append(note)
            try:
                base = load_policy(base_policy, base_config, tables=tables)
            except PolicyError as exc:
                raise DiffError(f"base policy is invalid: {exc}") from exc
        try:
            candidate = load_policy(args.policy, args.config, tables=tables)
        except PolicyError as exc:
            raise DiffError(f"candidate policy ({_rel(args.policy)}) is invalid: {exc}") from exc
    except DiffError as exc:
        print(f"policy_diff: {exc}\nUse --base-policy/--base-config or another --base ref.", file=sys.stderr)
        return 2

    ids = [c for c in args.customers.split(",") if c] or None
    changed = diff_decisions(base, candidate, tables, args.p_mode, ids)
    n = len(ids) if ids else len(tables["customer_master"])

    label_base = " + ".join(_rel(p) if p else f"{rel} @ {args.base}"
                            for p, rel in ((args.base_policy, "kg/policy.yaml"), (args.base_config, "config/kg.yaml")))
    label_cand = f"{_rel(args.policy)} + {_rel(args.config)}"
    lines = ["# Policy diff", "", f"Base: `{label_base}`. Candidate: `{label_cand}`."]
    lines += [f"Note: {x}." for x in notes]
    lines += ["", f"**{len(changed)} of {n} customers get a different decision.**", "",
              "| Customer | Before | After |", "|---|---|---|"]
    lines += [f"| {c} | {_md(b)} | {_md(a)} |" for c, b, a in changed]
    OUT_MD.parent.mkdir(exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(
        {"base": label_base, "candidate": label_cand, "customers": n, "notes": notes,
         "changed": [{"customer_id": c, "before": b, "after": a} for c, b, a in changed]},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for note in notes:
        print(f"note: {note}")
    for c, b, a in changed:
        print(f"{c}  {b}  ->  {a}")
    print(f"\n{len(changed)} of {n} customers change ({time.perf_counter() - start:.1f} s) -> out/policy_diff.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
