---
title: This site is a data pipeline
date: 2026-10-04
kind: article
tags: [meta, python, github-actions, medallion]
summary: Why my personal site is built by a bronze → silver → gold pipeline with data-quality gates, and what that buys me as someone who wants to write every day.
---

I spend my working days moving data through lakehouse layers, so when I sat down to build a personal site I built it the same way. Every page you see here is the output of a small medallion pipeline. It runs once a day on GitHub Actions, and again whenever I push a new post.

## The shape of it

```text
GitHub API ─▶ bronze ─▶ silver (MERGE) ─▶ gold ─▶ expectations ─▶ render
posts/*.md ───────────▶ silver ───────────┘                         │
profile.json ───────────────────────────────────────────────────────┘
```

- **Bronze** lands the raw API responses exactly as GitHub returned them, stamped with an ingestion time. Nothing is cleaned here. If something looks wrong later, this is what I replay from.
- **Silver** is where history lives. GitHub only shows you a rolling year of contributions and about 90 days of events, so each run `MERGE`s the new snapshot into tables that only grow: contributions keyed on date (a day's count keeps changing until the day ends), events keyed on id (insert-only), and one profile row per day.
- **Gold** holds the aggregates the pages need: streaks, the weekday rhythm, per-month totals, languages, and the writing stats from my own posts.
- **Expectations** run before anything is published. Content errors fail the build, for example a DAG edge pointing at a role that doesn't exist, or a skill in a role's stack that isn't in the skills catalog. Data warnings, like stale data or gaps in the calendar, show up on the site itself.

## Storage separated from compute

The code and the posts live on `main`. The silver and gold tables live on a separate `data` branch that only the pipeline writes to. That split keeps the daily bot commits out of my history, so I never have to pull before pushing a post. It also gives me an append-only, versioned copy of every table for free, which is just git.

## Why bother

Partly because it's fun. Mostly because the habits carry over:

1. **Idempotent runs.** Running the pipeline twice in a day changes nothing the second time. The MERGE is the whole trick.
2. **Soft and hard failures.** If GitHub's API is down, ingestion fails *softly*. The site still builds from yesterday's silver tables and the run is marked `SUCCEEDED_WITH_WARNINGS`. If I break the content, the run fails *hard* and nothing deploys.
3. **The site shows its own run history.** Open the Activity page and you'll see the Gantt chart for the run that built it.

## Writing every day

The point of all this plumbing is to make writing cheap. A post is a Markdown file:

```bash
make post title="Delta MERGE without the shuffle" note=1
# edit content/posts/2026-10-05-delta-merge-without-the-shuffle.md
git add content/posts && git commit -m "note: delta merge" && git push
```

A few minutes later it's live. Short daily notes are kept apart from long-form articles, and posts dated in the future wait for the morning run on their date, so I can write ahead.

If you want to poke at the data, the Playground page has a SQL console. Try `SELECT * FROM pipeline_runs`.
