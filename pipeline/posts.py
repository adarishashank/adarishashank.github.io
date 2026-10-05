"""Parse content/posts/*.md (front matter + Markdown) into post records.

Front matter is a small YAML subset, which is all a blog post needs:

    ---
    title: Comparing tables without ORDER BY
    date: 2026-10-04
    tags: [spark, data-quality]
    kind: note            # article | note
    summary: One line for the blog index and social previews.
    draft: false
    ---
"""
from __future__ import annotations

import re
from datetime import date

import markdown

from .common import POSTS_DIR, log, today_local

KINDS = {"article", "note"}
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _scalar(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    return v


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("front matter opened with --- but never closed")
    meta = {}
    for line in text[3:end].strip().splitlines():
        line = line.split("  #", 1)[0].rstrip()  # trailing comments need two spaces, so "PR #12" survives
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, val = line.partition(":")
        if not sep:
            raise ValueError(f"bad front matter line: {line!r}")
        meta[key.strip().lower()] = _scalar(val)
    return meta, text[end + 4:].lstrip("\n")


def _plain(md_text: str) -> str:
    text = re.sub(r"```.*?```", " ", md_text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#>*_~|-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_paragraph(md_text: str) -> str:
    for block in re.split(r"\n\s*\n", md_text):
        b = block.strip()
        if b and not b.startswith(("#", "```", "|", "!", "<", "- ", "* ", "1.")):
            return _plain(b)
    return ""


def _renderer():
    return markdown.Markdown(
        extensions=["fenced_code", "tables", "footnotes", "sane_lists", "attr_list", "admonition", "toc"],
        extension_configs={"toc": {"permalink": "#", "permalink_class": "anchor", "toc_depth": "2-3"}},
        output_format="html5",
    )


def parse_all(ctx: dict) -> dict:
    include_drafts = ctx.get("drafts", False)
    today = today_local()
    posts, skipped = [], {"draft": 0, "scheduled": 0}
    md = _renderer()

    for path in sorted(POSTS_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue  # templates and scratch files
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        where = f"{path.relative_to(POSTS_DIR.parent.parent)}"
        if not meta.get("title"):
            raise ValueError(f"{where}: missing 'title' in front matter")
        try:
            d = date.fromisoformat(str(meta.get("date") or path.name[:10]))
        except ValueError:
            raise ValueError(f"{where}: 'date' must look like 2026-10-04") from None

        if meta.get("draft") is True and not include_drafts:
            skipped["draft"] += 1
            continue
        if d > today and not include_drafts:
            skipped["scheduled"] += 1  # publishes automatically on the first run on/after its date
            continue

        kind = str(meta.get("kind", "article")).lower()
        if kind not in KINDS:
            raise ValueError(f"{where}: kind must be one of {sorted(KINDS)}, got {kind!r}")
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        md.reset()
        html = md.convert(body)
        words = len(_plain(body).split())
        slug = str(meta.get("slug") or _DATE_PREFIX.sub("", path.stem)).strip().lower()
        posts.append({
            "slug": slug,
            "title": str(meta["title"]),
            "date": d.isoformat(),
            "updated": str(meta["updated"]) if meta.get("updated") else None,
            "kind": kind,
            "tags": [str(t).lower() for t in tags],
            "summary": str(meta.get("summary") or _first_paragraph(body))[:280],
            "html": html,
            "toc": md.toc_tokens if hasattr(md, "toc_tokens") else [],
            "words": words,
            "reading_min": max(1, round(words / 220)),
            "draft": meta.get("draft") is True,
            "source": where,
        })

    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    for i, p in enumerate(reversed(posts)):
        p["version"] = i  # DESCRIBE HISTORY-style version number, oldest = 0
    ctx["posts"] = posts
    log("OK", f"posts: {len(posts)} published"
              + (f", {skipped['draft']} draft" if skipped["draft"] else "")
              + (f", {skipped['scheduled']} scheduled" if skipped["scheduled"] else ""))
    return {"published": len(posts), **skipped}
