"""Shared helpers: HTTP fetching, JSON files, dates."""
import gzip
import json
import os
import time
import urllib.request
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")          # cached historical results (committed)
SITE_DATA_DIR = os.path.join(ROOT, "site", "data")  # what the website reads

ESPN = "https://site.api.espn.com/apis"
UA = "Mozilla/5.0 (SportsPred; +https://github.com/amalmehta/SportsPred)"


def fetch(url, retries=3, as_json=True):
    """GET a URL (gzip-aware) with simple retries. Returns parsed JSON or text."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
            text = raw.decode("utf-8")
            return json.loads(text) if as_json else text
        except Exception as e:  # network hiccups: back off and retry
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("fetch failed: %s (%s)" % (url, last))


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj, compact=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        else:
            json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def today():
    """Today's date (UTC), overridable with SPORTSPRED_TODAY=YYYY-MM-DD for tests/replays."""
    forced = os.environ.get("SPORTSPRED_TODAY")
    if forced:
        return date.fromisoformat(forced)
    return datetime.now(timezone.utc).date()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def day(iso):
    """'2026-10-13T19:00Z' -> '2026-10-13'"""
    return iso[:10]
