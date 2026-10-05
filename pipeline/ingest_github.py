"""Bronze: land raw GitHub responses as-is, stamped with ingestion time.

Sources
  - REST  /users/{u}                      profile counters
  - REST  /users/{u}/repos                repository snapshot
  - REST  /users/{u}/events/public        last ~90 days of public activity
  - Contribution calendar, from GraphQL when a token is available (includes private
    contribution counts if the profile setting allows), else from the public HTML calendar.
"""
from __future__ import annotations

import html
import os
import re

from .common import BRONZE, http, iso, log, now_utc, write_json

GRAPHQL = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
    }
  }
}
"""


def _token() -> str | None:
    return os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _calendar_graphql(user: str, token: str) -> dict:
    resp = http("https://api.github.com/graphql", token=token, data={"query": GRAPHQL, "variables": {"login": user}})
    if resp.get("errors"):
        raise RuntimeError(resp["errors"][0].get("message", "GraphQL error"))
    coll = resp["data"]["user"]["contributionsCollection"]
    days = [
        {"date": d["date"], "count": d["contributionCount"]}
        for w in coll["contributionCalendar"]["weeks"]
        for d in w["contributionDays"]
    ]
    breakdown = {k: v for k, v in coll.items() if k != "contributionCalendar"}
    return {"source": "graphql", "days": days, "breakdown": breakdown}


_TD = re.compile(r"<td\b[^>]*\bdata-date=\"(\d{4}-\d{2}-\d{2})\"[^>]*>", re.S)
_ID = re.compile(r"\bid=\"([^\"]+)\"")
_LEVEL = re.compile(r"\bdata-level=\"(\d)\"")
_TIP = re.compile(r"<tool-tip\b[^>]*\bfor=\"([^\"]+)\"[^>]*>(.*?)</tool-tip>", re.S)
_COUNT = re.compile(r"^\s*([\d,]+)\s+contribution")


def _calendar_html(user: str) -> dict:
    page = http(f"https://github.com/users/{user}/contributions", accept="text/html")
    tips = {}
    for cell_id, text in _TIP.findall(page):
        m = _COUNT.match(html.unescape(text))
        tips[cell_id] = int(m.group(1).replace(",", "")) if m else 0
    days = []
    for m in _TD.finditer(page):
        tag = m.group(0)
        cell_id = (_ID.search(tag) or [None, None])[1]
        level = int((_LEVEL.search(tag) or [None, "0"])[1])
        count = tips.get(cell_id)
        if count is None:  # tooltip missing: fall back to "at least one" for non-zero levels
            count = 1 if level else 0
        days.append({"date": m.group(1), "count": count, "level": level})
    if not days:
        raise RuntimeError("contribution calendar markup not recognised")
    return {"source": "html", "days": days, "breakdown": {}}


def _paginate(url: str, token: str | None, max_pages: int = 5) -> list:
    out = []
    for page in range(1, max_pages + 1):
        sep = "&" if "?" in url else "?"
        batch = http(f"{url}{sep}per_page=100&page={page}", token=token)
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


def run(ctx: dict) -> dict:
    user = ctx["config"]["github"]["username"]
    token = _token()
    stamp = iso(now_utc())

    profile = http(f"https://api.github.com/users/{user}", token=token)
    repos = _paginate(f"https://api.github.com/users/{user}/repos?type=owner&sort=pushed", token)
    events = _paginate(f"https://api.github.com/users/{user}/events/public", token, max_pages=3)

    calendar = None
    if token:
        try:
            calendar = _calendar_graphql(user, token)
        except Exception as e:  # noqa: BLE001 - any failure falls through to the HTML path
            log("WARN", f"GraphQL calendar failed ({e}); falling back to public HTML calendar")
    if calendar is None:
        calendar = _calendar_html(user)

    for name, payload in (("profile", profile), ("repos", repos), ("events", events), ("calendar", calendar)):
        write_json(BRONZE / "github" / f"{name}.json", {"ingested_at": stamp, "user": user, "data": payload})

    ctx["bronze_ingested_at"] = stamp
    log("OK", f"bronze: profile, {len(repos)} repos, {len(events)} events, "
              f"{len(calendar['days'])} calendar days via {calendar['source']}")
    return {"repos": len(repos), "events": len(events), "calendar_days": len(calendar["days"]),
            "calendar_source": calendar["source"], "authenticated": bool(token)}
