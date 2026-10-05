"""Scaffold a post:  python -m pipeline.new_post "Title" [--note] [--tags a,b] [--date 2026-10-05]"""
from __future__ import annotations

import argparse
import re
import sys

from .common import POSTS_DIR, today_local


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--note", action="store_true", help="short daily note instead of a full article")
    ap.add_argument("--tags", default="", help="comma-separated, e.g. spark,delta")
    ap.add_argument("--date", default=today_local().isoformat(), help="YYYY-MM-DD; a future date schedules the post")
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args(argv)

    slug = re.sub(r"[^a-z0-9]+", "-", a.title.lower()).strip("-")[:60].strip("-")
    path = POSTS_DIR / f"{a.date}-{slug}.md"
    if path.exists():
        print(f"{path} already exists", file=sys.stderr)
        return 1
    tags = ", ".join(t.strip().lower() for t in a.tags.split(",") if t.strip())
    title = a.title.replace('"', "'")
    path.write_text(
        "---\n"
        f'title: "{title}"\n'
        f"date: {a.date}\n"
        f"kind: {'note' if a.note else 'article'}\n"
        f"tags: [{tags}]\n"
        "summary: \n"
        f"draft: {'true' if a.draft else 'false'}\n"
        "---\n\n"
        + ("What I learned today, in a few lines.\n" if a.note else "Intro paragraph.\n\n## The problem\n\n## What I did\n\n## Takeaways\n"),
        encoding="utf-8",
    )
    print(path.relative_to(POSTS_DIR.parent.parent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
