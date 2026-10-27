"""Deploy the engine to the Databricks workspace (docs/databricks.md §5).

  python scripts/databricks_deploy.py job [--run]   upload the code, create/update the job "maingau-nba-nightly"
  python scripts/databricks_deploy.py run           run the job now and wait for it
  python scripts/databricks_deploy.py genie [--ask "question"]   create/update the Genie space over maingau_nba
  python scripts/databricks_deploy.py app           the dashboard + API as the Databricks App "maingau-nba"
                                                    (build web/ first: cd web && npm run build)

The code goes to /Workspace/Users/<you>/maingau-nba (nba/, kg/, config/, templates/ and the job script). The job has
two tasks on serverless compute: validate_data (the data contract on maingau_raw), then decide_and_publish (feedback
from Delta, customer memory, every customer's decision, results to maingau_nba). Its 02:00 schedule starts paused,
so it never spends the Free Edition quota unless someone unpauses it.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from nba import lakehouse as lh  # noqa: E402

JOB_NAME = "maingau-nba-nightly"
CODE = ["nba/**/*.py", "kg/*.yaml", "config/*.yaml", "templates/**/*.yaml", "scripts/databricks_job.py", "requirements.txt"]
# Not databricks-sdk, pyspark or protobuf: serverless ships them as core packages and refuses an upgrade
# (ERROR_CORE_PACKAGE_VERSION_CHANGE). Inside the job the engine talks to Unity Catalog through Spark.
DEPENDENCIES = ["networkx>=3.2", "PyYAML>=6.0", "pydantic~=2.14.1", "ruamel.yaml>=0.18", "openpyxl>=3.1"]


def code_root(w) -> str:
    return f"/Users/{w.current_user.me().user_name}/maingau-nba"


def repo_files(patterns) -> list[Path]:
    return sorted({p for pattern in patterns for p in REPO.glob(pattern) if p.is_file() and "__pycache__" not in p.parts})


def upload_code(w, root: str | None = None, files: list[Path] | None = None, extra: dict[str, bytes] | None = None) -> str:
    """Copy repo files (default: the engine's) and generated files into a workspace folder; returns its /Workspace path."""
    from databricks.sdk.service.workspace import ImportFormat

    root = root or code_root(w)
    items = {p.relative_to(REPO).as_posix(): p.read_bytes() for p in (files if files is not None else repo_files(CODE))}
    items.update(extra or {})
    for folder in sorted({f"{root}/{rel}".rsplit("/", 1)[0] for rel in items}):
        w.workspace.mkdirs(folder)

    def put(item):
        from databricks.sdk.errors import ResourceExhausted

        rel, data = item
        for attempt in range(8):  # the workspace API rate-limits bursts (Free Edition especially): back off
            try:
                return w.workspace.upload(f"{root}/{rel}", data, format=ImportFormat.AUTO, overwrite=True)
            except ResourceExhausted:
                time.sleep(2 ** attempt)
        raise RuntimeError(f"upload of {rel} kept being rate-limited")

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(put, sorted(items.items())))
    print(f"Uploaded {len(items)} files to /Workspace{root}")
    return f"/Workspace{root}"


def job_settings(folder: str):
    from databricks.sdk.service import compute, jobs

    script = f"{folder}/scripts/databricks_job.py"

    def task(key, step, description, after=None):
        return jobs.Task(task_key=key, description=description, environment_key="nba",
                         depends_on=[jobs.TaskDependency(task_key=after)] if after else None,
                         spark_python_task=jobs.SparkPythonTask(python_file=script, parameters=["--step", step, "--repo", folder],
                                                                source=jobs.Source.WORKSPACE))

    return dict(
        name=JOB_NAME,
        description="MAINGAU Next Best Action: check the raw data, learn from feedback, decide for every customer, "
                    "publish to maingau_nba (scripts/databricks_job.py)",
        tasks=[task("validate_data", "validate", "Data contract (kg/data_contract.yaml) on maingau_raw"),
               task("decide_and_publish", "decide",
                    "Feedback from Delta -> customer memory -> decide for all customers -> maingau_nba", "validate_data")],
        environments=[jobs.JobEnvironment(environment_key="nba",
                                          spec=compute.Environment(environment_version="3", dependencies=DEPENDENCIES))],
        schedule=jobs.CronSchedule(quartz_cron_expression="0 0 2 * * ?", timezone_id="Europe/Berlin",
                                   pause_status=jobs.PauseStatus.PAUSED),
        max_concurrent_runs=1,
        tags={"project": "maingau-nba"},
    )


def find_job(w):
    return next(iter(w.jobs.list(name=JOB_NAME)), None)


def deploy_job(w) -> int:
    from databricks.sdk.service import jobs

    settings = job_settings(upload_code(w))
    found = find_job(w)
    if found:
        w.jobs.reset(found.job_id, new_settings=jobs.JobSettings(**settings))
        print(f"Updated job {JOB_NAME} ({found.job_id})")
        return found.job_id
    job_id = w.jobs.create(**settings).job_id
    print(f"Created job {JOB_NAME} ({job_id})")
    return job_id


def run_job(w, job_id: int) -> int:
    from databricks.sdk.errors import OperationFailed

    print("Running... (serverless start and dependency install take a few minutes the first time)")
    waiter = w.jobs.run_now(job_id)
    try:
        waiter.result(timeout=timedelta(minutes=45))
    except OperationFailed as exc:
        print(f"Failed: {' '.join(str(exc).split())[:600]}")
    run = w.jobs.get_run(waiter.response.run_id)
    print(f"Run {run.run_id}: {run.state.result_state.value if run.state.result_state else run.state.life_cycle_state.value}")
    print(f"  {run.run_page_url}")
    for t in sorted(run.tasks or [], key=lambda t: t.start_time or 0):
        secs = ((t.end_time or 0) - (t.start_time or 0)) / 1000
        print(f"  {t.task_key:20s} {t.state.result_state.value if t.state.result_state else '?':10s} {secs:6.0f}s")
    return 0 if run.state.result_state and run.state.result_state.value == "SUCCESS" else 1


GENIE_TITLE = "MAINGAU Next Best Action"
GENIE_INSTRUCTIONS = """\
This space answers questions about MAINGAU's Next Best Action results: which action the engine proposes for each
customer, what it is worth, and why other actions are blocked. Mock data, snapshot 30 Sep 2026.
Tables:
- worklist: one row per customer with the proposed action (chosen_offer, chosen_tuple, channel, tone), its expected
  value delta_clv in EUR, p_accept, the urgency tier (P1 most urgent ... P5) and the segment (archetype A0-A5).
- nba_options: every allowed action per customer, ranked by expected delta_clv; chosen = true marks the proposal.
- nba_blocked: actions a rule removed, with rule_id and a plain-language reason.
- decision_log: approvals, overrides and rejections by marketers and service agents.
- product_catalog: product names; join product_catalog.product_id to offer_id or chosen_offer.
Rules for answers:
- Money is in EUR. "Value", "expected value" or "gain" means delta_clv. Round to 2 decimals.
- chosen_offer = 'NO_ACTION' means the customer should not be contacted; leave it out when asked about offers or
  value, and say how many customers it concerns.
- P-SV-01 (Service-Only) is a service contact by a service agent, not a sales offer: when asked about offers or sales,
  leave it out and mention the service cases separately.
- Show offer names next to offer IDs.
- channel values: outbound_call (= phone call), sms, email, newsletter_email, app_push, portal_popup,
  service_agent (handled by a service agent). "Phone" means outbound_call.
- Hard rules (consent, exclusions, contact cap) can never be overridden; explain a block with nba_blocked.reason.
- If a value is missing, say "not enough data"; never guess.
"""
GENIE_EXAMPLES = [
    ("Which offers bring the most expected value in total?",
     "SELECT w.chosen_offer AS offer_id, p.product_name, COUNT(*) AS customers,\n"
     "       ROUND(SUM(w.delta_clv), 2) AS total_expected_value_eur\n"
     "FROM {out}.worklist w JOIN {raw}.product_catalog p ON p.product_id = w.chosen_offer\n"
     "WHERE w.chosen_offer NOT IN ('NO_ACTION', 'P-SV-01')\nGROUP BY ALL\nORDER BY total_expected_value_eur DESC"),
    ("Why is StromWärme blocked for so many customers?",
     "SELECT rule_id, COUNT(DISTINCT customer_id) AS customers, ANY_VALUE(reason) AS example_reason\n"
     "FROM {out}.nba_blocked\nWHERE offer_id = 'P-EN-03'\nGROUP BY rule_id\nORDER BY customers DESC"),
    ("Show the 10 most urgent customers and what we propose",
     "SELECT customer_id, urgency_tier, urgency_score, archetype_name, top_reason, chosen_tuple,\n"
     "       ROUND(delta_clv, 2) AS expected_value_eur\n"
     "FROM {out}.worklist\nORDER BY urgency_tier, urgency_score DESC\nLIMIT 10"),
]
GENIE_QUESTIONS = [
    "Which offers bring the most expected value in total?",
    "Show the 10 most urgent customers and what we propose",
    "Why is StromWärme blocked for so many customers?",
    "How many customers would we contact by phone or SMS, and what is it worth?",
    "Which segments get a sales offer, and what is the average expected value per segment?",
    "What did people approve or reject so far?",
]


def genie_space(s: lh.Settings) -> str:
    """The space definition (Genie's serialized format, version 2); lists are sorted as the API expects."""
    import json
    import uuid

    out, raw = f"{s.catalog}.{s.out_schema}", f"{s.catalog}.{s.raw_schema}"
    lines = lambda text: text.splitlines(keepends=True)  # noqa: E731
    ids = sorted(uuid.uuid4().hex for _ in range(len(GENIE_QUESTIONS) + len(GENIE_EXAMPLES) + 1))
    space = {
        "version": 2,
        "config": {"sample_questions": [{"id": ids[i], "question": [q]} for i, q in enumerate(GENIE_QUESTIONS)]},
        "data_sources": {"tables": [{"identifier": t} for t in sorted(
            [f"{out}.worklist", f"{out}.nba_options", f"{out}.nba_blocked", f"{out}.decision_log", f"{raw}.product_catalog"])]},
        "instructions": {
            "text_instructions": [{"id": ids[len(GENIE_QUESTIONS)], "content": lines(GENIE_INSTRUCTIONS)}],
            "example_question_sqls": [
                {"id": ids[len(GENIE_QUESTIONS) + 1 + i], "question": [q], "sql": lines(sql.format(out=out, raw=raw))}
                for i, (q, sql) in enumerate(GENIE_EXAMPLES)],
        },
    }
    return json.dumps(space, ensure_ascii=False)


def deploy_genie(w, s: lh.Settings) -> str:
    warehouse = lh.Warehouse(s, w).warehouse_id
    description = ("Ask MAINGAU's Next Best Action results in plain language: proposed actions, expected value, "
                   "urgency, segments and why actions are blocked. Read-only, governed by Unity Catalog.")
    found = next((sp for sp in w.genie.list_spaces().spaces or [] if sp.title == GENIE_TITLE), None)
    kwargs = dict(serialized_space=genie_space(s), title=GENIE_TITLE, description=description, warehouse_id=warehouse)
    if found:
        w.genie.update_space(found.space_id, **kwargs)
        space_id = found.space_id
        print(f"Updated Genie space {GENIE_TITLE} ({space_id})")
    else:
        space_id = w.genie.create_space(**kwargs).space_id
        print(f"Created Genie space {GENIE_TITLE} ({space_id})")
    print(f"  {w.config.host.rstrip('/')}/genie/rooms/{space_id}")
    return space_id


def ask_genie(w, space_id: str, question: str) -> None:
    msg = w.genie.start_conversation_and_wait(space_id, question)
    print(f"Q: {question}  [{msg.status.value if msg.status else '?'}]")
    for a in msg.attachments or []:
        if a.text and a.text.content:
            print(f"A: {a.text.content}")
        if a.query and a.query.query:
            print("SQL:\n  " + a.query.query.replace("\n", "\n  "))
            result = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, msg.message_id,
                                                                 a.attachment_id)
            rows = (result.statement_response.result.data_array or []) if result.statement_response and \
                result.statement_response.result else []
            for row in rows[:8]:
                print("  ", row)


APP_NAME = "maingau-nba"
APP_YAML = """\
command: ["python", "scripts/databricks_app.py"]
env:
  - name: MAINGAU_DATA_SOURCE
    value: databricks
  - name: MAINGAU_DATABRICKS_WAREHOUSE
    valueFrom: sql-warehouse
  - name: MAINGAU_LLM
    value: none
"""


def app_files() -> list[Path]:
    """Engine + API + the built dashboard. In API mode the dashboard reads everything from the API except the
    Knowledge Base graph (kg_viz.json), so the 27 MB of static customer JSON stays behind."""
    dist = [p for p in repo_files(["web/dist/**/*"])
            if "data" not in p.relative_to(REPO / "web" / "dist").parts or p.name == "kg_viz.json"]
    return repo_files(CODE + ["api/*.py", "scripts/databricks_app.py"]) + dist


def app_requirements() -> bytes:
    lines = [ln for ln in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#") and not ln.startswith("pytest")]
    return ("\n".join(lines + ["databricks-sdk>=0.50"]) + "\n").encode()


def grant_app(s: lh.Settings, w, principal: str) -> None:
    """Unity Catalog access for the App's service principal: read the raw data and the results, append decisions."""
    wh, who = lh.Warehouse(s, w), f"`{principal}`"
    catalog, raw, out = lh.q(s.catalog), lh.q(s.raw_schema), lh.q(s.out_schema)
    for sql in (f"GRANT USE CATALOG ON CATALOG {catalog} TO {who}",
                f"GRANT USE SCHEMA, SELECT ON SCHEMA {catalog}.{raw} TO {who}",
                f"GRANT USE SCHEMA, SELECT, MODIFY, CREATE TABLE ON SCHEMA {catalog}.{out} TO {who}"):
        wh.query(sql)
    print(f"Granted Unity Catalog access to the App's service principal {principal}")


def deploy_app(w, s: lh.Settings) -> int:
    from databricks.sdk.errors import NotFound
    from databricks.sdk.service import apps

    if not (REPO / "web" / "dist" / "index.html").exists():
        raise SystemExit("web/dist is missing: run `cd web && npm run build` first")
    folder = upload_code(w, f"{code_root(w)}-app", app_files(),
                         {"app.yaml": APP_YAML.encode(), "requirements.txt": app_requirements()})
    try:
        app = w.apps.get(APP_NAME)
    except NotFound:
        warehouse = lh.Warehouse(s, w).warehouse_id
        print(f"Creating the App {APP_NAME} (its compute starts too; a few minutes)...")
        app = w.apps.create_and_wait(app=apps.App(
            name=APP_NAME, description="MAINGAU Next Best Action: worklist, Customer 360, groups and approvals",
            resources=[apps.AppResource(name="sql-warehouse", sql_warehouse=apps.AppResourceSqlWarehouse(
                id=warehouse, permission=apps.AppResourceSqlWarehouseSqlWarehousePermission.CAN_USE))]))
    grant_app(s, w, app.service_principal_client_id)
    if not app.compute_status or app.compute_status.state != apps.ComputeState.ACTIVE:
        print("Starting the App's compute...")
        w.apps.start_and_wait(APP_NAME)
    print("Deploying (installs requirements, then starts the server)...")
    deployment = w.apps.deploy_and_wait(APP_NAME, apps.AppDeployment(source_code_path=folder))
    state = deployment.status.state.value if deployment.status and deployment.status.state else "?"
    print(f"Deployment {state}: {deployment.status.message if deployment.status else ''}")
    print(f"  {w.apps.get(APP_NAME).url}")
    return 0 if state == "SUCCEEDED" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("job", help="upload the code and create/update the job")
    j.add_argument("--run", action="store_true", help="run it right after deploying")
    sub.add_parser("run", help="run the job now and wait")
    sub.add_parser("app", help="deploy the dashboard + API as a Databricks App")
    g = sub.add_parser("genie", help="create/update the Genie space over maingau_nba")
    g.add_argument("--ask", action="append", default=[], help="ask the space a question afterwards (repeatable)")
    args = ap.parse_args()
    s = lh.load_settings()
    w = lh.workspace_client(s)
    if args.cmd == "app":
        return deploy_app(w, s)
    if args.cmd == "genie":
        space_id = deploy_genie(w, s)
        for question in args.ask:
            ask_genie(w, space_id, question)
        return 0
    if args.cmd == "job":
        job_id = deploy_job(w)
        return run_job(w, job_id) if args.run else 0
    found = find_job(w)
    if not found:
        ap.error(f"no job {JOB_NAME}: run `job` first")
    return run_job(w, found.job_id)


if __name__ == "__main__":
    sys.exit(main())
