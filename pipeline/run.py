"""Orchestrator: runs the site's DAG and records each run like a job-run history.

    python -m pipeline.run              full run: GitHub ingest -> silver -> gold -> DQ -> render
    python -m pipeline.run --offline    skip network tasks; rebuild from the silver tables already on disk
    python -m pipeline.run --drafts     also publish draft and future-dated posts (local preview only)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

from . import build_site, ingest_github, posts, quality, transform
from .common import GOLD, iso, load_config, load_profile, log, now_utc, read_json, write_json

MAX_RUNS = 30

# name, callable, upstream, flags
#   network: needs the internet; skipped with --offline
#   soft:    a failure degrades the run (site still builds from cached data) instead of failing it
TASKS = [
    ("bronze.ingest_github", ingest_github.run, [], {"network", "soft"}),
    ("silver.merge_github", transform.merge_silver, ["bronze.ingest_github"], {"network", "soft"}),
    ("silver.parse_posts", posts.parse_all, [], set()),
    ("gold.aggregate", transform.build_gold, ["silver.merge_github", "silver.parse_posts"], set()),
    ("quality.expectations", quality.run, ["gold.aggregate"], set()),
    ("serve.render_site", build_site.run, ["quality.expectations"], set()),
]


def _run_id() -> str:
    n = os.environ.get("GITHUB_RUN_NUMBER")
    return f"#{n}" if n else "local-" + now_utc().strftime("%Y%m%d-%H%M%S")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="skip GitHub ingestion, use cached silver data")
    ap.add_argument("--drafts", action="store_true", help="include drafts and scheduled posts")
    ap.add_argument("--no-record", action="store_true", help="don't append this run to pipeline_runs.json")
    args = ap.parse_args(argv)

    record = not (args.offline or args.no_record or args.drafts)
    started = now_utc()
    t0 = time.perf_counter()
    ctx = {"config": load_config(), "profile": load_profile(), "drafts": args.drafts}
    history = read_json(GOLD / "pipeline_runs.json", [])

    this_run = {
        "run_id": _run_id(),
        "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "commit": (os.environ.get("GITHUB_SHA") or "")[:7] or None,
        "started_at": iso(started),
        "status": "RUNNING",
        "duration_ms": None,
        "tasks": [],
    }
    # The site shows its own build in the run history; the render task is filled in after it finishes.
    ctx["runs"] = ([this_run] + history)[:MAX_RUNS] if record else history

    log("INFO", f"run {this_run['run_id']} ({this_run['trigger']}) started"
                + (" [offline]" if args.offline else "") + (" [drafts]" if args.drafts else ""))
    status: dict[str, str] = {}
    flags_of = {name: flags for name, _, _, flags in TASKS}
    hard_failure = False

    for name, fn, upstream, flags in TASKS:
        task = {"name": name, "status": None, "duration_ms": 0, "metrics": {}, "error": None}
        this_run["tasks"].append(task)
        failed_up = [u for u in upstream if status.get(u) in ("FAILED", "UPSTREAM_FAILED", "SKIPPED")]
        hard_up = [u for u in failed_up if status[u] != "SKIPPED" and "soft" not in flags_of[u]]

        if args.offline and "network" in flags:
            task["status"] = "SKIPPED"
            task["error"] = "offline"
        elif hard_up:
            task["status"] = "UPSTREAM_FAILED"
            hard_failure = True
        elif failed_up and "network" in flags:
            task["status"] = "SKIPPED"  # don't merge bronze that this run failed to refresh
            task["error"] = f"upstream {failed_up[0]} did not succeed"
        else:
            ts = time.perf_counter()
            try:
                task["metrics"] = fn(ctx) or {}
                task["status"] = "SUCCEEDED"
            except Exception as e:  # noqa: BLE001 - recorded, then decided by the soft flag
                task["status"] = "FAILED"
                task["error"] = str(e)[:300]
                log("FAIL", f"{name}: {e}")
                if os.environ.get("PIPELINE_DEBUG"):
                    traceback.print_exc()
                hard_failure |= "soft" not in flags
            task["duration_ms"] = round((time.perf_counter() - ts) * 1000)
        status[name] = task["status"]
        if task["status"] == "SUCCEEDED":
            log("OK", f"{name} ({task['duration_ms']} ms)")
        elif task["status"] == "SKIPPED":
            log("INFO", f"{name} skipped: {task['error']}")

    soft_failure = any(t["status"] == "FAILED" for t in this_run["tasks"])
    dq = ctx.get("dq") or {}
    this_run["dq"] = {k: dq.get(k) for k in ("passed", "total", "warnings")} if dq else None
    this_run["status"] = ("FAILED" if hard_failure
                          else "SUCCEEDED_WITH_WARNINGS" if soft_failure or dq.get("warnings")
                          else "SUCCEEDED")
    this_run["duration_ms"] = round((time.perf_counter() - t0) * 1000)

    if record:
        ctx["runs"] = ([this_run] + history)[:MAX_RUNS]
        write_json(GOLD / "pipeline_runs.json", ctx["runs"])
        if status.get("serve.render_site") == "SUCCEEDED":
            build_site.run(ctx)  # second pass so the page shows this run's final timings

    log("OK" if not hard_failure else "FAIL",
        f"run {this_run['run_id']} {this_run['status']} in {this_run['duration_ms']} ms")
    return 1 if hard_failure else 0


if __name__ == "__main__":
    sys.exit(main())
