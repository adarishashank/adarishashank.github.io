"""Shared plumbing: paths, config, logging, HTTP and small file helpers."""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
POSTS_DIR = CONTENT / "posts"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = Path(os.environ.get("SITE_OUT", ROOT / "_site"))

# The lakehouse lives in ./data locally; CI points this at a checkout of the `data` branch.
LAKE = Path(os.environ.get("LAKEHOUSE_DIR", ROOT / "data"))
BRONZE = LAKE / "bronze"
SILVER = LAKE / "silver"
GOLD = LAKE / "gold"


def load_config() -> dict:
    return read_json(ROOT / "site.config.json")


def load_profile() -> dict:
    return read_json(CONTENT / "profile.json")


# ---------------------------------------------------------------- time

IST = timezone(timedelta(hours=5, minutes=30))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_local():
    """'Today' in IST: posts dated today publish, posts dated tomorrow wait for the next run."""
    return datetime.now(IST).date()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- logging

_COLORS = {"INFO": "\033[36m", "OK": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m"}


def log(level: str, msg: str) -> None:
    color = _COLORS.get(level, "") if sys.stdout.isatty() else ""
    reset = "\033[0m" if color else ""
    print(f"{color}[{level:>4}]{reset} {msg}", flush=True)


# ---------------------------------------------------------------- files

def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, separators=None if indent else (",", ":"))
        f.write("\n")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})
    tmp.replace(path)


# ---------------------------------------------------------------- http

def http(url: str, *, token: str | None = None, data: dict | None = None,
         accept: str = "application/vnd.github+json", retries: int = 3, timeout: int = 20):
    """GET (or POST when data is given) with exponential backoff on transient failures.
    Returns parsed JSON for JSON responses, text otherwise."""
    headers = {"User-Agent": "shashank-lakehouse-pipeline", "Accept": accept}
    if "api.github.com" in url:
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        if token:
            headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                ctype = resp.headers.get("Content-Type", "")
                return json.loads(raw) if "json" in ctype else raw
        except urllib.error.HTTPError as e:
            last_err = e
            # 4xx (other than rate limiting) will not fix itself on retry.
            if e.code < 500 and e.code not in (403, 429):
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_err}")
