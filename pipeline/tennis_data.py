"""Fetch ATP/WTA singles results and draws from ESPN's public tennis scoreboard."""
import os
from datetime import date, timedelta

from . import config
from .common import DATA_DIR, ESPN, fetch, read_json, today, write_json

TENNIS_CACHE = os.path.join(DATA_DIR, "tennis")
SINGLES = {"atp": "mens-singles", "wta": "womens-singles"}


def _status(st):
    name = st.get("name", "")
    if "WALKOVER" in name:
        return "walkover"
    if "RETIRED" in name:
        return "retired"
    if st.get("state") == "post" and st.get("completed"):
        return "final"
    if st.get("state") == "in":
        return "live"
    if st.get("state") == "post":
        return "cancelled"
    return "scheduled"


def parse_event(e, tour):
    matches = []
    for g in e.get("groupings", []):
        if (g.get("grouping") or {}).get("slug") != SINGLES[tour]:
            continue
        for c in g.get("competitions", []):
            comp = sorted(c.get("competitors", []), key=lambda x: x.get("order", 0))
            if len(comp) != 2:
                continue
            ids = [x.get("id") for x in comp]
            names = [(x.get("athlete") or {}).get("displayName") or "TBD" for x in comp]
            known = [i if i and not str(i).startswith("-") and n != "TBD" else None for i, n in zip(ids, names)]
            w = None
            if comp[0].get("winner"):
                w = 0
            elif comp[1].get("winner"):
                w = 1
            matches.append({
                "id": c.get("id"), "round": (c.get("round") or {}).get("displayName", ""),
                "date": c.get("date") or e.get("date"), "status": _status((c.get("status") or {}).get("type") or {}),
                "a": known[0], "an": names[0] if known[0] else "TBD",
                "b": known[1], "bn": names[1] if known[1] else "TBD", "w": w,
            })
    prev = [p.get("displayName") for p in e.get("previousWinners", [])
            if (p.get("type") or {}).get("slug") == SINGLES[tour]]
    return {"id": "%s-%s" % (tour, e.get("id")), "tour": tour, "name": e.get("name"), "start": e.get("date"), "end": e.get("endDate"),
            "major": bool(e.get("major")), "defending": prev[0] if prev else None, "matches": matches}


def fetch_day(tour, d):
    data = fetch("%s/site/v2/sports/tennis/%s/scoreboard?dates=%s" % (ESPN, tour, d.strftime("%Y%m%d")))
    return [parse_event(e, tour) for e in data.get("events", [])]


def load_tour(tour, first=None, ahead_days=45, step=3):
    """Every event for a tour from `first` until `ahead_days` from now.

    Events that ended more than two weeks ago are frozen on disk, so only recent dates are refetched.
    """
    first = first or date.fromisoformat(config.TENNIS_HISTORY_FROM)
    t = today()
    folder = os.path.join(TENNIS_CACHE, tour)
    index_path = os.path.join(folder, "_fetched_days.json")
    fetched = set(read_json(index_path, []))
    events = {}
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        if name.endswith(".json") and not name.startswith("_"):
            ev = read_json(os.path.join(folder, name))
            events[ev["id"]] = ev
    frozen_before = (t - timedelta(days=14)).isoformat()
    d = first
    n_fetch = 0
    while d <= t + timedelta(days=ahead_days):
        iso = d.isoformat()
        if iso in fetched:
            d += timedelta(days=step)
            continue
        try:
            for ev in fetch_day(tour, d):
                old = events.get(ev["id"])
                # keep the richer copy (draws grow as the event goes on)
                if old is None or len(ev["matches"]) >= len(old["matches"]) or ev["end"][:10] >= frozen_before:
                    events[ev["id"]] = ev
            n_fetch += 1
            if iso < frozen_before:
                fetched.add(iso)
        except RuntimeError as err:
            print("  ! %s %s: %s" % (tour, iso, err))
        d += timedelta(days=step)
    for ev in events.values():
        if ev["end"] and ev["end"][:10] < frozen_before:
            write_json(os.path.join(folder, "%s.json" % ev["id"]), ev)
    write_json(index_path, sorted(fetched))
    print("  tennis %s: %d events (%d day queries)" % (tour, len(events), n_fetch))
    return sorted(events.values(), key=lambda e: e["start"] or "")
