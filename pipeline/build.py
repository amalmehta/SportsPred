"""SportsPred daily build: fetch results, rate teams and players, simulate, write site/data/*.json.

    python -m pipeline.build              # everything
    python -m pipeline.build --only tennis
"""
import argparse
import os
from datetime import datetime, timedelta, timezone
import time
import traceback

from . import live_log, soccer_build, tennis_build
from .common import SITE_DATA_DIR, now_iso, read_json, today, write_json


def summary(c):
    return {k: c.get(k) for k in ("id", "sport", "name", "group", "status", "season", "tour", "country",
                                  "start", "end", "favourite", "next_match", "champion", "slam", "surface", "projected", "format", "stale", "updated")}


def search_index(summaries):
    """Every team and player on the site, for the home page's search: name -> where they appear."""
    found = {}
    for s in summaries:
        c = read_json(os.path.join(SITE_DATA_DIR, s["sport"], s["id"] + ".json"))
        if not c:
            continue
        key = "p_qualify" if c.get("format") == "qualifying" else "p_win"
        who = "player" if c["sport"] == "tennis" else "team"
        for r in c.get("table", []):
            found.setdefault(r[who], []).append({
                "id": c["id"], "sport": c["sport"], "name": c["name"], "p": r.get(key, 0.0),
                "what": "qualify" if key == "p_qualify" else "win", "out": r.get("alive") is False,
                "status": c.get("status")})
    return [{"n": n, "in": sorted(v, key=lambda e: -e["p"])} for n, v in sorted(found.items())]


def today_digest(summaries, hours=36, min_move=0.03):
    """Home page digest: the next day and a half of matches everywhere, and the biggest odds moves
    between the last two days the site published (from each competition's live log)."""
    now = datetime.now(timezone.utc)
    soon = (now + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%MZ")
    since = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%MZ")  # keep games that may still be on
    matches, movers = [], []
    for s in summaries:
        c = read_json(os.path.join(SITE_DATA_DIR, s["sport"], s["id"] + ".json"))
        if not c:
            continue
        where = {"id": c["id"], "sport": c["sport"], "comp": c["name"], "group": c.get("group"), "country": c.get("country")}
        for m in c.get("upcoming", []):
            if since <= (m.get("date") or "") <= soon:
                matches.append(dict(m, **where))
        live = c.get("live") or []
        if len(live) >= 2:
            before, after = live[-2], live[-1]
            for team in set(before["p"]) | set(after["p"]):
                a, b = before["p"].get(team, 0.0), after["p"].get(team, 0.0)
                if abs(b - a) >= min_move:
                    movers.append(dict(where, team=team, before=a, after=b, since=before["date"],
                                       what="qualify" if c.get("format") == "qualifying" else "win"))
    matches.sort(key=lambda m: m["date"])
    movers.sort(key=lambda m: -abs(m["after"] - m["before"]))
    return {"updated": now_iso(), "matches": matches, "movers": movers[:8]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["clubs", "international", "tennis"], action="append")
    args = ap.parse_args(argv)
    parts = args.only or ["clubs", "international", "tennis"]
    today_iso = today().isoformat()
    index_path = os.path.join(SITE_DATA_DIR, "index.json")
    model_path = os.path.join(SITE_DATA_DIR, "model.json")
    index = read_json(index_path, {"competitions": []})
    model = read_json(model_path, {})
    kept = {c["id"]: c for c in index.get("competitions", [])}

    steps = {
        "clubs": (soccer_build.build_clubs, soccer_build.write, "soccer_clubs",
                  lambda c: c["sport"] == "soccer" and c["group"] in ("domestic", "european")),
        "international": (soccer_build.build_international, soccer_build.write, "soccer_international",
                          lambda c: c["group"] in ("international", "qualifying")),
        "tennis": (tennis_build.build, tennis_build.write, "tennis", lambda c: c["sport"] == "tennis"),
    }
    failed = []
    for name in parts:
        build, write, model_key, belongs = steps[name]
        t0 = time.time()
        print("== %s" % name)
        try:
            comps, m = build(today_iso)
        except Exception:
            # keep yesterday's predictions for this part rather than publishing nothing
            traceback.print_exc()
            failed.append(name)
            continue
        write(live_log.attach(comps, today_iso))
        kept = {k: v for k, v in kept.items() if not belongs(v)}
        kept.update({c["id"]: summary(c) for c in comps})
        model[model_key] = m
        print("   %d competitions in %.0fs" % (len(comps), time.time() - t0))

    write_json(index_path, {"updated": now_iso(), "date": today_iso, "competitions": list(kept.values())}, compact=False)
    model["updated"] = now_iso()
    write_json(model_path, model, compact=False)
    write_json(os.path.join(SITE_DATA_DIR, "search.json"), search_index(kept.values()))
    write_json(os.path.join(SITE_DATA_DIR, "today.json"), today_digest(kept.values()), compact=False)
    if failed:
        raise SystemExit("failed: %s" % ", ".join(failed))


if __name__ == "__main__":
    main()
