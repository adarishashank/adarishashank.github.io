"""Silver: MERGE bronze into history tables.   Gold: site-ready aggregates.

Silver tables (append/upsert, never truncated, so history outlives GitHub's API windows)
  github_contributions.csv   date, count, updated_at          MERGE ON date
  github_events.jsonl        id, type, repo, created_at, ...  MERGE ON id (insert-only)
  github_profile_daily.csv   date, followers, ...             MERGE ON date
  github_repos.json          current snapshot                 overwrite (SCD1)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from .common import BRONZE, GOLD, SILVER, iso, log, now_utc, read_csv, read_json, read_jsonl, \
    today_local, write_csv, write_json, write_jsonl

MAX_EVENTS = 3000


# ================================================================ silver

def _merge_rows(existing: list[dict], incoming: list[dict], key: str, compare: list[str]):
    """MERGE INTO existing USING incoming ON key: update changed rows, insert new ones."""
    by_key = {r[key]: r for r in existing}
    inserted = updated = 0
    for row in incoming:
        cur = by_key.get(row[key])
        if cur is None:
            by_key[row[key]] = row
            inserted += 1
        elif any(str(cur.get(c)) != str(row.get(c)) for c in compare):
            by_key[row[key]] = {**cur, **row}
            updated += 1
    return sorted(by_key.values(), key=lambda r: r[key]), inserted, updated


def _event_summary(e: dict) -> str:
    t, p = e.get("type", ""), e.get("payload") or {}
    ref = (p.get("ref") or "").replace("refs/heads/", "")
    if t == "PushEvent":
        n = p.get("size") or p.get("distinct_size") or len(p.get("commits") or [])
        msg = ((p.get("commits") or [{}])[-1].get("message") or "").split("\n")[0]
        head = f"pushed {n} commit{'s' if n != 1 else ''} to {ref}" if n else f"pushed to {ref or 'a branch'}"
        return f"{head}: {msg}" if msg else head
    if t == "CreateEvent":
        return f"created {p.get('ref_type', 'ref')} {p.get('ref') or ''}".strip()
    if t == "DeleteEvent":
        return f"deleted {p.get('ref_type', 'ref')} {p.get('ref') or ''}".strip()
    if t == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        return f"{p.get('action', '')} PR #{pr.get('number', '')}: {pr.get('title', '')}".strip()
    if t == "PullRequestReviewEvent":
        return f"reviewed PR #{(p.get('pull_request') or {}).get('number', '')}"
    if t == "IssuesEvent":
        i = p.get("issue") or {}
        return f"{p.get('action', '')} issue #{i.get('number', '')}: {i.get('title', '')}"
    if t == "IssueCommentEvent":
        return f"commented on #{(p.get('issue') or {}).get('number', '')}"
    if t == "WatchEvent":
        return "starred the repo"
    if t == "ForkEvent":
        return "forked the repo"
    if t == "ReleaseEvent":
        return f"released {(p.get('release') or {}).get('tag_name', '')}"
    if t == "PublicEvent":
        return "made the repo public"
    return t.replace("Event", "").lower()


def merge_silver(ctx: dict) -> dict:
    bronze = BRONZE / "github"
    if not (bronze / "calendar.json").exists():
        raise RuntimeError("no bronze data to merge (run without --offline first)")
    stamp = read_json(bronze / "calendar.json")["ingested_at"]
    metrics = {}

    # contributions: MERGE ON date (a day's count changes until the day is over)
    cal = read_json(bronze / "calendar.json")["data"]
    incoming = [{"date": d["date"], "count": int(d["count"]), "updated_at": stamp} for d in cal["days"]]
    rows, ins, upd = _merge_rows(read_csv(SILVER / "github_contributions.csv"), incoming, "date", ["count"])
    write_csv(SILVER / "github_contributions.csv", rows, ["date", "count", "updated_at"])
    metrics["contributions"] = {"rows": len(rows), "inserted": ins, "updated": upd}
    write_json(SILVER / "github_calendar_meta.json",
               {"source": cal["source"], "breakdown": cal.get("breakdown", {}), "ingested_at": stamp})

    # events: insert-only MERGE ON id
    raw_events = read_json(bronze / "events.json")["data"]
    incoming = [{
        "id": e["id"], "type": e["type"], "repo": e["repo"]["name"], "created_at": e["created_at"],
        "summary": _event_summary(e), "public": e.get("public", True),
    } for e in raw_events]
    rows, ins, _ = _merge_rows(read_jsonl(SILVER / "github_events.jsonl"), incoming, "id", [])
    rows.sort(key=lambda r: r["created_at"])
    rows = rows[-MAX_EVENTS:]
    write_jsonl(SILVER / "github_events.jsonl", rows)
    metrics["events"] = {"rows": len(rows), "inserted": ins}

    # repos: overwrite snapshot, keeping only what the site needs
    repos = [{
        "name": r["name"], "description": r.get("description") or "", "language": r.get("language"),
        "stars": r.get("stargazers_count", 0), "forks": r.get("forks_count", 0),
        "fork": r.get("fork", False), "archived": r.get("archived", False),
        "pushed_at": r.get("pushed_at"), "created_at": r.get("created_at"),
        "url": r.get("html_url"), "topics": r.get("topics") or [], "homepage": r.get("homepage") or "",
    } for r in read_json(bronze / "repos.json")["data"]]
    write_json(SILVER / "github_repos.json", repos)
    metrics["repos"] = {"rows": len(repos)}

    # profile: one row per day, MERGE ON date
    p = read_json(bronze / "profile.json")["data"]
    snap = {
        "date": today_local().isoformat(), "followers": p.get("followers", 0), "following": p.get("following", 0),
        "public_repos": p.get("public_repos", 0),
        "stars": sum(r["stars"] for r in repos if not r["fork"]),
        "contributions_last_year": sum(int(d["count"]) for d in cal["days"]),
    }
    fields = list(snap.keys())
    rows, ins, upd = _merge_rows(read_csv(SILVER / "github_profile_daily.csv"), [snap], "date", fields[1:])
    write_csv(SILVER / "github_profile_daily.csv", rows, fields)
    write_json(SILVER / "github_profile.json", {
        "login": p.get("login"), "name": p.get("name"), "avatar_url": p.get("avatar_url"),
        "html_url": p.get("html_url"), "created_at": p.get("created_at"), "bio": p.get("bio"),
    })
    metrics["profile_daily"] = {"rows": len(rows), "inserted": ins, "updated": upd}

    log("OK", "silver: " + ", ".join(
        f"{k} ({v['rows']} rows" + (f", +{v['inserted']}" if v.get("inserted") else "")
        + (f", ~{v['updated']}" if v.get("updated") else "") + ")" for k, v in metrics.items()))
    return metrics


# ================================================================ gold

def _streaks(counts: dict[date, int], today: date):
    longest = (0, None, None)
    run, start, prev = 0, None, None
    for d in sorted(counts):
        if counts[d] > 0:
            if run and prev and (d - prev) == timedelta(days=1):
                run += 1
            else:
                run, start = 1, d
            if run > longest[0]:
                longest = (run, start, d)
        else:
            run = 0
        prev = d
    # current streak: today may still be empty, so count back from yesterday in that case
    cur, d = 0, today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    while counts.get(d, 0) > 0:
        cur += 1
        d -= timedelta(days=1)
    return cur, longest


def _levels(values: list[int]) -> list[int]:
    """Thresholds for a 0–4 heatmap scale from quartiles of the non-zero days."""
    nz = sorted(v for v in values if v > 0)
    if not nz:
        return [1, 2, 3, 4]
    q = [nz[min(len(nz) - 1, int(len(nz) * f))] for f in (0.25, 0.5, 0.75)]
    t = [1]
    for v in q:
        t.append(max(v, t[-1] + 1))
    return t  # level n means count >= t[n-1]


def _calendar(counts: dict[date, int], today: date, days: int = 371):
    start = today - timedelta(days=days - 1)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # align to a Sunday, like GitHub
    out, d = [], start
    while d <= today:
        out.append({"d": d.isoformat(), "c": counts.get(d, 0)})
        d += timedelta(days=1)
    return out


def build_gold(ctx: dict) -> dict:
    today = today_local()
    contributions = read_csv(SILVER / "github_contributions.csv")
    counts = {date.fromisoformat(r["date"]): int(r["count"]) for r in contributions}
    events = read_jsonl(SILVER / "github_events.jsonl")
    repos = read_json(SILVER / "github_repos.json", [])
    profile = read_json(SILVER / "github_profile.json", {})
    meta = read_json(SILVER / "github_calendar_meta.json", {})
    daily = read_csv(SILVER / "github_profile_daily.csv")

    year_ago = today - timedelta(days=364)
    last_year = {d: c for d, c in counts.items() if year_ago <= d <= today}
    cur_streak, (long_n, long_s, long_e) = _streaks(counts, today)
    best = max(last_year.items(), key=lambda kv: (kv[1], kv[0]), default=(None, 0))

    weekday = [0] * 7  # Mon..Sun
    for d, c in last_year.items():
        weekday[d.weekday()] += c

    monthly = []
    y, m = today.year, today.month
    for _ in range(12):
        key = f"{y:04d}-{m:02d}"
        monthly.append({"m": key, "c": sum(c for d, c in counts.items() if d.strftime("%Y-%m") == key)})
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    monthly.reverse()

    own = [r for r in repos if not r["fork"]]
    langs = Counter(r["language"] for r in own if r["language"])

    created = profile.get("created_at")
    stats = {
        "refreshed_at": meta.get("ingested_at"),
        "source": meta.get("source", "cache"),
        "breakdown": meta.get("breakdown", {}),
        "tracked_since": daily[0]["date"] if daily else None,
        "profile": {
            **profile,
            "followers": int(daily[-1]["followers"]) if daily else 0,
            "following": int(daily[-1]["following"]) if daily else 0,
            "public_repos": int(daily[-1]["public_repos"]) if daily else len(repos),
            "stars": sum(r["stars"] for r in own),
            "member_years": round((today - date.fromisoformat(created[:10])).days / 365.25, 1) if created else None,
        },
        "totals": {
            "last_year": sum(last_year.values()),
            "ytd": sum(c for d, c in counts.items() if d.year == today.year and d <= today),
            "last_30": sum(c for d, c in counts.items() if today - timedelta(days=29) <= d <= today),
            "active_days": sum(1 for c in last_year.values() if c > 0),
            "all_time_tracked": sum(counts.values()),
            "best_day": {"d": best[0].isoformat() if best[0] else None, "c": best[1]},
        },
        "streak": {
            "current": cur_streak, "longest": long_n,
            "longest_start": long_s.isoformat() if long_s else None,
            "longest_end": long_e.isoformat() if long_e else None,
        },
        "levels": _levels(list(last_year.values())),
        "calendar": _calendar(counts, today),
        "weekday": weekday,
        "monthly": monthly,
        "languages": [{"name": k, "repos": v} for k, v in langs.most_common(8)],
        "repos": sorted(own, key=lambda r: r["pushed_at"] or "", reverse=True)[:8],
        "events": list(reversed(events[-30:])),
        "daily": daily[-120:],
    }
    write_json(GOLD / "github_stats.json", stats)
    ctx["github"] = stats

    # writing activity rolls up from the posts parsed earlier in this run
    posts = ctx.get("posts", [])
    per_day = defaultdict(int)
    for p in posts:
        per_day[date.fromisoformat(p["date"])] += 1
    w_cur, (w_long, _, _) = _streaks(dict(per_day), today)
    writing = {
        "posts": len(posts),
        "articles": sum(1 for p in posts if p["kind"] == "article"),
        "notes": sum(1 for p in posts if p["kind"] == "note"),
        "words": sum(p["words"] for p in posts),
        "last_30": sum(1 for p in posts if date.fromisoformat(p["date"]) >= today - timedelta(days=29)),
        "streak": w_cur, "longest_streak": w_long,
        "levels": [1, 2, 3, 4],
        "calendar": _calendar(dict(per_day), today),
        "tags": Counter(t for p in posts for t in p["tags"]).most_common(20),
    }
    write_json(GOLD / "writing_stats.json", writing)
    ctx["writing"] = writing

    log("OK", f"gold: {stats['totals']['last_year']} contributions/yr, streak {cur_streak}d, "
              f"{len(stats['events'])} events, {writing['posts']} posts")
    return {"calendar_days": len(stats["calendar"]), "events": len(stats["events"]),
            "repos": len(stats["repos"]), "posts": writing["posts"]}
