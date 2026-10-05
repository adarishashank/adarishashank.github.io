"""Serve: render the static site into _site/ from content, gold tables and templates."""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, time
from email.utils import format_datetime
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import figures
from .common import IST, OUT, STATIC, TEMPLATES, iso, log, now_utc, today_local
from .figure_specs import DIAGRAMS, OPS_LOOP

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


# ---------------------------------------------------------------- helpers

def fmt_month(ym: str | None) -> str:
    if not ym:
        return "Present"
    y, m = ym.split("-")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def months_between(start: str, end: str | None) -> int:
    t = today_local()
    y1, m1 = map(int, start.split("-")[:2])
    y2, m2 = map(int, end.split("-")[:2]) if end else (t.year, t.month)
    return max(1, (y2 - y1) * 12 + (m2 - m1) + 1)


def duration_label(months: int) -> str:
    y, m = divmod(months, 12)
    parts = ([f"{y} yr"] if y else []) + ([f"{m} mo"] if m else [])
    return " ".join(parts) or "1 mo"


def fmt_date(d: str, style: str = "long") -> str:
    dt = date.fromisoformat(d[:10])
    if style == "short":
        return f"{dt.day} {MONTHS[dt.month - 1]}"
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- model

def _experience(profile: dict) -> list[dict]:
    out = []
    for e in profile["experience"]:
        months = months_between(e["start"], e["end"])
        out.append({
            **e,
            "period": e.get("period_label") or f"{fmt_month(e['start'])} – {fmt_month(e['end'])}",
            "months": months,
            "duration": duration_label(months),
            "first_metric": next((h["metric"] for h in e["highlights"] if h.get("metric")), None),
        })
    return out


def _catalog(profile: dict, experience: list[dict]) -> list[dict]:
    lineage: dict[str, list[str]] = {}
    for e in experience:
        for s in e["stack"]:
            lineage.setdefault(s, []).append(e["id"])
    schemas = []
    for key, schema in profile["skills"].items():
        schemas.append({
            "key": key, "label": schema["label"],
            "items": [{"name": s, "fqn": f"shashank.{key}.{snake(s)}", "used_in": lineage.get(s, [])}
                      for s in schema["items"]],
        })
    return schemas


def _tables(ctx: dict, experience: list[dict], catalog: list[dict]) -> dict:
    """Everything the in-browser SQL console can query. Column types drive sorting and alignment."""
    profile, posts = ctx["profile"], ctx.get("posts", [])
    gh = ctx.get("github") or {}

    def table(desc, cols, rows):
        return {"description": desc, "columns": [{"name": n, "type": t} for n, t in cols], "rows": rows}

    t = {}
    t["experience"] = table(
        "Roles, projects, education and certifications: the nodes of the career pipeline.",
        [("id", "string"), ("stage", "string"), ("kind", "string"), ("org", "string"), ("role", "string"),
         ("client", "string"), ("project", "string"), ("start_month", "string"), ("end_month", "string"),
         ("months", "int"), ("status", "string")],
        [[e["id"], e["stage"], e["kind"], e["org"], e["role"], e.get("client"), e["project"], e["start"],
          e["end"], e["months"], e["status"]] for e in experience])
    t["highlights"] = table(
        "What was delivered in each role, one row per bullet.",
        [("experience_id", "string"), ("n", "int"), ("text", "string"), ("metric", "string")],
        [[e["id"], i + 1, h["text"], h.get("metric")] for e in experience for i, h in enumerate(e["highlights"])])
    t["skills"] = table(
        "The skills catalog. used_in lists the experience ids that used the skill (lineage).",
        [("name", "string"), ("schema", "string"), ("fqn", "string"), ("used_in_count", "int"), ("used_in", "string")],
        [[i["name"], s["key"], i["fqn"], len(i["used_in"]), ", ".join(i["used_in"])] for s in catalog for i in s["items"]])
    t["metrics"] = table(
        "Headline numbers from the resume.",
        [("value", "string"), ("unit", "string"), ("label", "string"), ("source", "string")],
        [[m["value"], m["unit"], m["label"], m["source"]] for m in profile["metrics"]])
    t["certifications"] = table(
        "Certifications.", [("name", "string"), ("issuer", "string"), ("valid", "string")],
        [[c["name"], c["issuer"], c["valid"]] for c in profile["certifications"]])
    t["awards"] = table(
        "Awards and recognition.", [("title", "string"), ("org", "string"), ("year", "string"), ("detail", "string")],
        [[a["title"], a["org"], a["year"] or None, a["detail"]] for a in profile["awards"]])
    t["services"] = table(
        "Services I offer. Pick one on the Services page.",
        [("id", "string"), ("name", "string"), ("format", "string"), ("duration", "string"), ("tags", "string")],
        [[s["id"], s["name"], s["format"], s["duration"], ", ".join(s["tags"])] for s in profile["services"]])
    t["posts"] = table(
        "Published blog posts and notes.",
        [("date", "date"), ("title", "string"), ("kind", "string"), ("tags", "string"), ("words", "int"),
         ("reading_min", "int"), ("slug", "string")],
        [[p["date"], p["title"], p["kind"], ", ".join(p["tags"]), p["words"], p["reading_min"], p["slug"]] for p in posts])
    t["github_daily"] = table(
        "GitHub contributions per day (last ~53 weeks), refreshed daily by the pipeline.",
        [("date", "date"), ("contributions", "int"), ("weekday", "string")],
        [[c["d"], c["c"], date.fromisoformat(c["d"]).strftime("%a")] for c in gh.get("calendar", [])])
    t["github_repos"] = table(
        "Public repositories I own (forks excluded), most recently pushed first.",
        [("name", "string"), ("language", "string"), ("stars", "int"), ("forks", "int"), ("pushed_at", "timestamp"),
         ("description", "string")],
        [[r["name"], r["language"], r["stars"], r["forks"], r["pushed_at"], r["description"] or None]
         for r in gh.get("repos", [])])
    t["github_events"] = table(
        "Recent public GitHub events, merged into history so they outlive the API's 90-day window.",
        [("created_at", "timestamp"), ("type", "string"), ("repo", "string"), ("summary", "string")],
        [[e["created_at"], e["type"], e["repo"], e["summary"]] for e in gh.get("events", [])])
    t["pipeline_runs"] = table(
        "Runs of the pipeline that built this site.",
        [("run_id", "string"), ("trigger", "string"), ("started_at", "timestamp"), ("duration_ms", "int"),
         ("status", "string"), ("dq_passed", "int"), ("dq_total", "int")],
        [[r["run_id"], r["trigger"], r["started_at"], r["duration_ms"], r["status"],
          (r.get("dq") or {}).get("passed"), (r.get("dq") or {}).get("total")] for r in ctx.get("runs", [])])
    return t


# ---------------------------------------------------------------- feeds

def _rss(site: dict, posts: list[dict], url) -> str:
    items = []
    for p in posts[: site["blog"]["feed_items"]]:
        link = url(f"blog/{p['slug']}/", absolute=True)
        pub = format_datetime(datetime.combine(date.fromisoformat(p["date"]), time(9, 0), IST))
        cats = "".join(f"<category>{escape(t)}</category>" for t in p["tags"])
        items.append(
            f"<item><title>{escape(p['title'])}</title><link>{link}</link><guid>{link}</guid>"
            f"<pubDate>{pub}</pubDate><description>{escape(p['summary'])}</description>{cats}</item>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{escape(site['author']['name'])} — blog</title><link>{url('blog/', absolute=True)}</link>"
        f"<description>{escape(site['description'])}</description><language>{site['lang']}</language>"
        f'<atom:link href="{url("feed.xml", absolute=True)}" rel="self" type="application/rss+xml"/>'
        f"<lastBuildDate>{format_datetime(now_utc())}</lastBuildDate>{''.join(items)}</channel></rss>\n")


def _sitemap(pages: list[str], posts: list[dict], url) -> str:
    today = today_local().isoformat()
    locs = [(url(p, absolute=True), today) for p in pages]
    locs += [(url(f"blog/{p['slug']}/", absolute=True), p["updated"] or p["date"]) for p in posts]
    body = "".join(f"<url><loc>{escape(u)}</loc><lastmod>{d}</lastmod></url>" for u, d in locs)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def _figures(profile: dict, experience: list[dict]) -> dict:
    figs = {spec["id"]: figures.diagram(spec) for spec in DIAGRAMS}
    figs["ops-loop"] = figures.ops_loop(OPS_LOOP["stages"], OPS_LOOP["value"], OPS_LOOP["label"])
    figs["timeline"] = figures.timeline(experience)
    figs["skillflow"] = figures.skill_flow(profile, experience)
    return figs


# ---------------------------------------------------------------- render

def run(ctx: dict) -> dict:
    site, profile = ctx["config"], ctx["profile"]
    base = "/" + site.get("base_path", "/").strip("/") + "/"
    base = "/" if base == "//" else base
    origin = site["url"].rstrip("/")

    def url(path: str = "", absolute: bool = False) -> str:
        u = base + path.lstrip("/")
        return origin + u if absolute else u

    experience = _experience(profile)
    by_id = {e["id"]: e for e in experience}
    catalog = _catalog(profile, experience)
    posts = ctx.get("posts", [])
    tables = _tables(ctx, experience, catalog)

    stages = [{**s, "nodes": [e for e in experience if e["stage"] == s["id"]]} for s in profile["stages"]]
    current = next((e for e in experience if e["status"] == "RUNNING"), experience[0])

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters.update(month=fmt_month, date=fmt_date, snake=snake, slugify=slugify,
                       compact=lambda n: f"{n / 1000:.1f}k" if n >= 1000 else str(n),
                       plural=lambda n, word: f"{n} {word}" + ("" if n == 1 else "s"),
                       unit=lambda n, word: word + ("" if n == 1 else "s"))
    env.globals.update(
        url=url, site=site, profile=profile, build_time=iso(now_utc()), today=today_local().isoformat(), ICONS=figures.ICONS,
        ficon=lambda name, x, y, size=20, cls="fi": Markup(figures.icon(name, x, y, size, cls)),
        asset_v=re.sub(r"\D", "", iso(now_utc()))[:12],
        avatar_abs=url(site["author"]["avatar"], absolute=True),
    )

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(STATIC, OUT / "static")

    common = {
        "github": ctx.get("github") or {}, "writing": ctx.get("writing") or {},
        "runs": ctx.get("runs", []), "dq": ctx.get("dq") or {}, "posts": posts,
    }
    pages = 0

    def write(rel: str, text: str):
        nonlocal pages
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        pages += rel.endswith(".html")

    figs = _figures(profile, experience)
    jobs = [e for e in sorted(experience, key=lambda e: e["start"], reverse=True) if e["kind"] == "job"]
    metrics_by = {}
    for m in profile["metrics"]:
        metrics_by.setdefault(m["source"], []).append(m)
    common.update(figs=figs, jobs=jobs, experience=experience, by_id=by_id, current=current,
                  metrics_by=metrics_by, catalog=catalog)

    def page(rel: str, template: str, name: str, **extra):
        write(rel, env.get_template(template).render(page=name, **common, **extra))

    skill_use = {}
    for j in jobs:
        for sk in j["stack"]:
            skill_use[sk] = skill_use.get(sk, 0) + 1
    common.update(skill_use=skill_use)
    page("index.html", "index.html", "home")
    page("activity/index.html", "activity.html", "activity")
    page("playground/index.html", "playground.html", "playground", table_names=sorted(tables), tables_meta=tables)
    page("blog/index.html", "blog_index.html", "blog", all_tags=sorted({t for p in posts for t in p["tags"]}))

    chronological = list(reversed(posts))
    for i, p in enumerate(chronological):
        page(f"blog/{p['slug']}/index.html", "post.html", "post", post=p,
             prev=chronological[i - 1] if i > 0 else None,
             next=chronological[i + 1] if i + 1 < len(chronological) else None)

    write("404.html", env.get_template("404.html").render(page="404", **common))
    write("feed.xml", _rss(site, posts, url))
    write("sitemap.xml", _sitemap(["", "activity/", "playground/", "blog/"], posts, url))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {url('sitemap.xml', absolute=True)}\n")
    write("data/tables.json", json.dumps(tables, ensure_ascii=False, separators=(",", ":")))
    write(".nojekyll", "")
    if site.get("custom_domain"):
        write("CNAME", site["custom_domain"].strip() + "\n")

    log("OK", f"render: {pages} pages, {len(tables)} SQL tables -> {OUT.relative_to(OUT.parent)}/")
    return {"pages": pages, "tables": len(tables)}
