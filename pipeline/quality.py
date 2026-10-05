"""Expectations over silver/gold and the hand-written content.

'error' expectations fail the run (and the deploy) because they mean the site would be
wrong, e.g. a typo in profile.json. 'warn' expectations are reported on the site.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from .common import SILVER, read_csv, read_jsonl


def _check(name: str, severity: str, ok: bool, detail: str) -> dict:
    return {"name": name, "severity": severity, "passed": bool(ok), "detail": detail}


def run(ctx: dict) -> dict:
    profile = ctx["profile"]
    checks = []

    # ---- content integrity (errors)
    ids = {e["id"] for e in profile["experience"]}
    bad_edges = [f"{a}->{b}" for a, b in profile["edges"] if a not in ids or b not in ids]
    checks.append(_check("profile.edges_reference_nodes", "error", not bad_edges,
                         "all DAG edges resolve" if not bad_edges else f"unknown nodes in {bad_edges}"))

    catalog = {s for schema in profile["skills"].values() for s in schema["items"]}
    unknown = sorted({s for e in profile["experience"] for s in e["stack"] if s not in catalog})
    checks.append(_check("profile.stack_in_catalog", "error", not unknown,
                         "every stack item exists in the skills catalog" if not unknown
                         else f"not in catalog: {unknown}"))

    slugs = Counter(p["slug"] for p in ctx.get("posts", []))
    dupes = [s for s, n in slugs.items() if n > 1]
    checks.append(_check("posts.unique_slug", "error", not dupes,
                         f"{len(slugs)} unique slugs" if not dupes else f"duplicate slugs: {dupes}"))

    # ---- data expectations (warnings)
    rows = read_csv(SILVER / "github_contributions.csv")
    dates = [r["date"] for r in rows]
    checks.append(_check("contributions.unique_date", "warn", len(dates) == len(set(dates)),
                         f"{len(dates)} rows, {len(set(dates))} distinct dates"))
    negative = sum(1 for r in rows if int(r["count"]) < 0)
    checks.append(_check("contributions.non_negative", "warn", negative == 0, f"{negative} negative counts"))

    if dates:
        ds = sorted(date.fromisoformat(d) for d in dates)
        window = [d for d in ds if d >= ds[-1] - timedelta(days=364)]
        gaps = sum(1 for a, b in zip(window, window[1:]) if (b - a).days != 1)
        checks.append(_check("contributions.contiguous_365d", "warn", gaps == 0,
                             f"{gaps} gaps in the last 365 days of history"))

    refreshed = (ctx.get("github") or {}).get("refreshed_at")
    if refreshed:
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(refreshed.replace("Z", "+00:00"))).total_seconds() / 3600
        checks.append(_check("github.freshness_48h", "warn", age_h <= 48, f"data is {age_h:.1f}h old"))
    else:
        checks.append(_check("github.freshness_48h", "warn", False, "no GitHub data ingested yet"))

    events = read_jsonl(SILVER / "github_events.jsonl")
    ev_ids = [e["id"] for e in events]
    checks.append(_check("events.unique_id", "warn", len(ev_ids) == len(set(ev_ids)), f"{len(ev_ids)} events"))

    failed_errors = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    result = {
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "warnings": sum(1 for c in checks if not c["passed"] and c["severity"] == "warn"),
        "checks": checks,
    }
    ctx["dq"] = result
    if failed_errors:
        raise RuntimeError("; ".join(f"{c['name']}: {c['detail']}" for c in failed_errors))
    return {"passed": result["passed"], "total": result["total"], "warnings": result["warnings"]}
