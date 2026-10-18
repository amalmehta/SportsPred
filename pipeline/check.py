"""Sanity-check site/data before it's published. Any problem fails the run, so the live site keeps
its last good version instead of showing broken predictions.

    python -m pipeline.check
"""
import os
import sys
from datetime import datetime, timedelta, timezone

from . import config
from .common import SITE_DATA_DIR, fetch, read_json

TOL = 0.02


def problems_in(c):
    """Everything wrong with one competition file (an empty list means it's fine)."""
    out = []
    name = c.get("name") or c.get("id")
    table = c.get("table") or []
    key = "player" if c.get("sport") == "tennis" else "team"
    for r in table:
        for k in ("p_win", "p_qualify", "p_playoff", "p_sf", "p_top", "p_drop", "p_ko"):
            v = r.get(k)
            if v is not None and not (0.0 <= v <= 1.0):
                out.append("%s: %s has %s = %s" % (name, r.get(key), k, v))
    awaiting = c.get("sport") == "tennis" and not c.get("favourite")  # no draw yet
    total = sum(r.get("p_win", 0.0) for r in table)
    if c.get("format") == "qualifying":
        groups = len({r.get("group") for r in table})
        if abs(total - groups) > TOL * groups:
            out.append("%s: group-winner chances add up to %.3f, not %d" % (name, total, groups))
        direct = (c.get("slots") or {}).get("direct", 0)
        q = sum(r.get("p_qualify", 0.0) for r in table)
        if direct and abs(q - groups * direct) > TOL * groups * direct:
            out.append("%s: qualifying chances add up to %.3f, not %d" % (name, q, groups * direct))
    elif not awaiting:
        if not table:
            out.append("%s: no teams or players" % name)
        elif abs(total - 1.0) > TOL:
            out.append("%s: title chances add up to %.3f, not 1" % (name, total))
    places = c.get("places") or {}
    for key, field in (("top", "p_top"), ("drop", "p_drop"), ("ko", "p_ko")):
        n = places.get(key)
        if n and table and any(field in r for r in table):
            got = sum(r.get(field, 0.0) for r in table)
            if abs(got - n) > TOL * n:
                out.append("%s: %s chances add up to %.3f, not %d" % (name, field, got, n))
    for m in c.get("upcoming") or []:
        p = m.get("p")
        if isinstance(p, list) and abs(sum(p) - 1.0) > TOL:
            out.append("%s: %s v %s chances add up to %.3f" % (name, m.get("home"), m.get("away"), sum(p)))
        elif isinstance(p, (int, float)) and not (0.0 <= p <= 1.0):
            out.append("%s: %s v %s chance %s" % (name, m.get("a"), m.get("b"), p))
    return out


def vanished(local_index, published_index, now=None):
    """Competitions the live site shows as still going that this build has dropped.

    A failed fetch can make a league quietly disappear; finished events are allowed to drop off.
    """
    now = now or datetime.now(timezone.utc)
    recent = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    have = {c["id"] for c in local_index.get("competitions", [])}
    gone = []
    for c in published_index.get("competitions", []):
        still_on = c.get("status") in ("live", "upcoming") and (c.get("next_match") or "9999")[:10] >= recent
        if still_on and c["id"] not in have:
            gone.append(c.get("name") or c["id"])
    return gone


def check(data_dir=SITE_DATA_DIR, compare_live=True):
    index = read_json(os.path.join(data_dir, "index.json"))
    if not index or not index.get("competitions"):
        return ["index.json is missing or lists no competitions"]
    out = []
    sports = {c["sport"] for c in index["competitions"]}
    for sport in ("soccer", "tennis"):
        if sport not in sports:
            out.append("no %s competitions in index.json" % sport)
    for extra in ("search.json", "today.json", "model.json"):
        if read_json(os.path.join(data_dir, extra)) is None:
            out.append("%s is missing" % extra)
    if compare_live and config.SITE_URL:
        try:
            published = fetch(config.SITE_URL + "data/index.json", retries=2)
        except RuntimeError:
            published = None  # first publish, or the site is unreachable: nothing to compare with
        for name in vanished(index, published or {}):
            out.append("%s is still running on the live site but missing from this build" % name)
    for summary in index["competitions"]:
        c = read_json(os.path.join(data_dir, summary["sport"], summary["id"] + ".json"))
        if c is None:
            out.append("%s: listed in index.json but its file is missing" % summary["id"])
            continue
        out.extend(problems_in(c))
    return out


def main():
    found = check()
    for p in found:
        print("PROBLEM:", p)
    if found:
        sys.exit("%d problem(s): not publishing" % len(found))
    print("site/data looks good")


if __name__ == "__main__":
    main()
