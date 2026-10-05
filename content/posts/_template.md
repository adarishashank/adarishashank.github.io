---
title: "Your title here"
date: 2026-10-05
kind: note            # note = short daily log, article = long-form
tags: [databricks, spark]
summary: One sentence for the blog index, RSS and link previews.
draft: true           # set to false (or delete the line) to publish
---

Files starting with an underscore are ignored by the build, so this one never publishes.
Copy it, or run:  make post title="My title"   (add note=1 for a short note)

A post dated in the future is held back and publishes automatically on the first daily
run on or after that date (00:05 IST), so you can write ahead and schedule.

## Markdown you can use

- **bold**, *italic*, `inline code`, [links](https://example.com)
- fenced code blocks with a language for highlighting:

```sql
SELECT region, COUNT(*) FROM sales GROUP BY region
```

| tables | work | too |
|---|---|---|
| a | b | c |

!!! note "Admonitions"
    Indented four spaces under a `!!! note` line.

Footnotes work as well.[^1]

[^1]: Like this.
