"""Keep each day's live odds next to the replay.

The replay redraws the whole season from what was known each day, so it changes if the model
changes. The live log keeps what the site actually published, one entry per day per competition,
so the two can be compared later. The published site is the store: each run reads the previous
log from the local copy and from the live site, merges them, and adds today's entry.
"""
import os

from . import config
from .common import SITE_DATA_DIR, fetch, now_iso, read_json

MIN_P = 0.0005  # leave out teams/players with no real chance, to keep files small


def headline(c):
    """{name: chance} for the number the competition's chart tracks."""
    key = "p_qualify" if c.get("format") == "qualifying" else "p_win"
    name = "player" if c["sport"] == "tennis" else "team"
    return {r[name]: round(r[key], 4) for r in c["table"] if r.get(key, 0) >= MIN_P}


def previous(c):
    """Earlier entries for this competition: local copy plus the published site, merged by date."""
    rel = "%s/%s.json" % (c["sport"], c["id"])
    found = []
    local = read_json(os.path.join(SITE_DATA_DIR, rel), {}) or {}
    found.extend(local.get("live", []))
    if config.SITE_URL:
        try:
            found.extend((fetch(config.SITE_URL + "data/" + rel, retries=1) or {}).get("live", []))
        except RuntimeError:
            pass  # first publish, or the site is unreachable: start from what we have
    return found


def previous_file(sport, comp_id):
    """The last good copy of a competition: the newer of the local file and the live site's."""
    rel = "%s/%s.json" % (sport, comp_id)
    found = [read_json(os.path.join(SITE_DATA_DIR, rel))]
    if config.SITE_URL:
        try:
            found.append(fetch(config.SITE_URL + "data/" + rel, retries=1))
        except RuntimeError:
            pass
    found = [f for f in found if f]
    return max(found, key=lambda f: f.get("updated", "")) if found else None


def stale_copy(sport, comp_id, reason):
    """Last good copy, marked as not refreshed this run (None if there isn't one)."""
    old = previous_file(sport, comp_id)
    if old:
        old = dict(old, stale=True, stale_reason=reason)
    return old


def merge(entries, season):
    """One entry per date (the latest wins), only from the current season, oldest first."""
    by_date = {}
    for e in entries:
        if e.get("season") != season or not e.get("date"):
            continue
        if e["date"] not in by_date or e.get("t", "") > by_date[e["date"]].get("t", ""):
            by_date[e["date"]] = e
    return [by_date[d] for d in sorted(by_date)]


def attach(comps, today_iso, use_previous=True):
    """Add today's entry to each competition's `live` log (skipped when replaying a past date)."""
    if os.environ.get("SPORTSPRED_TODAY"):
        return comps
    for c in comps:
        if c.get("stale"):
            continue  # not refreshed this run: don't log yesterday's odds as today's
        season = c.get("season") or c.get("start", "")[:4]
        entry = {"date": today_iso[:10], "t": now_iso(), "season": season, "p": headline(c)}
        c["live"] = merge((previous(c) if use_previous else []) + [entry], season)
    return comps
