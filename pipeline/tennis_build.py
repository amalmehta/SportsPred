"""Build tennis predictions: player ratings, title odds per tournament, odds over time."""
import hashlib
import math
import os
from datetime import date, timedelta

from . import config
from .common import SITE_DATA_DIR, day, now_iso, write_json
from .tennis_data import load_tour
from .tennis_model import (TennisElo, as_of, best_of_five, main_draw, rated_matches,
                           simulate_draw, win_prob)


def seed_for(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def is_covered(ev, tour):
    return any(k.lower() in (ev["name"] or "").lower() for k in config.TENNIS_TOURS[tour]["keywords"])


def is_slam(ev):
    return any(s in (ev["name"] or "") for s in config.GRAND_SLAMS)


def event_payload(ev, tour, elo, snaps, today_iso):
    rounds = main_draw(ev)
    bo5 = tour == "atp" and is_slam(ev)
    players = {}
    for _, ms in rounds:
        for m in ms:
            for slot in ("a", "b"):
                if m[slot]:
                    players[m[slot]] = m[slot + "n"]
    finished = [m for _, ms in rounds for m in ms if m["status"] in ("final", "retired", "walkover")]
    final_round = rounds[-1][1] if rounds else []
    champion = None
    if final_round and final_round[0]["status"] in ("final", "retired", "walkover") and final_round[0]["w"] is not None:
        f = final_round[0]
        champion = f["a"] if f["w"] == 0 else f["b"]

    now = simulate_draw(rounds, elo.ratings, bo5, config.SIMS_TODAY, seed_for(ev["id"], today_iso[:10])) if rounds else {}

    series_days, series = [], []
    if rounds:
        days = sorted({day(m["date"]) for m in finished if day(m["date"]) < today_iso[:10]})
        first = min((day(m["date"]) for _, ms in rounds for m in ms if m["date"]), default=None)
        if first:
            pre = (date.fromisoformat(first) - timedelta(days=1)).isoformat()
            for d in [pre] + days:
                if d not in snaps:
                    continue
                series.append(simulate_draw(as_of(ev, d), snaps[d], bo5, config.SIMS_REPLAY, seed_for(ev["id"], d)))
                series_days.append(d)
        series_days.append(today_iso[:10])
        series.append(now)

    lost = set()
    for m in finished:
        if m["w"] is not None and m["a"] and m["b"]:
            lost.add(m["b"] if m["w"] == 0 else m["a"])
    rows = sorted(({"player": players[p], "id": p, "rating": round(elo.ratings.get(p, 1500)),
                    "p_win": round(now.get(p, 0.0), 4), "alive": p not in lost} for p in players),
                  key=lambda r: (-r["p_win"], not r["alive"], -r["rating"]))

    def p_match(a, b):
        p = win_prob(elo.ratings.get(a, 1500), elo.ratings.get(b, 1500))
        return best_of_five(p) if bo5 else p

    upcoming = []
    for name, ms in rounds:
        for m in sorted(ms, key=lambda m: m["date"] or ""):
            if m["status"] in ("scheduled", "live") and m["a"] and m["b"]:
                upcoming.append({"date": m["date"], "round": name, "a": m["an"], "b": m["bn"],
                                 "p": round(p_match(m["a"], m["b"]), 3), "live": m["status"] == "live"})
    recent = []
    for m in sorted(finished, key=lambda m: (m["date"] or "", m["id"]), reverse=True)[:12]:
        if m["id"] in elo.pre and m["w"] is not None:
            ra, rb = elo.pre[m["id"]]
            p = win_prob(ra, rb)
            p = best_of_five(p) if bo5 else p
            recent.append({"date": m["date"], "round": m["round"], "a": m["an"], "b": m["bn"], "w": m["w"],
                           "p": round(p, 3), "called": (p >= 0.5) == (m["w"] == 0)})

    top = sorted({p for s in series for p in s}, key=lambda p: -max(s.get(p, 0) for s in series))[:8]
    t = today_iso[:10]
    if champion:
        status = "finished"
    elif not rounds or (ev["start"] or "")[:10] > t:
        status = "upcoming"
    else:
        status = "live"
    fav = rows[0] if rows and rows[0]["p_win"] > 0 else None
    return {
        "id": ev["id"], "sport": "tennis", "tour": config.TENNIS_TOURS[tour]["name"], "name": ev["name"],
        "group": tour + ("-slam" if is_slam(ev) else "-1000"), "start": ev["start"], "end": ev["end"],
        "slam": is_slam(ev), "best_of": 5 if bo5 else 3, "updated": now_iso(), "status": status,
        "defending": ev.get("defending"), "champion": players.get(champion) if champion else None,
        "table": rows, "upcoming": upcoming[:30], "recent": recent,
        "history": {"dates": series_days,
                    "series": [{"team": players.get(p, p), "p": [round(s.get(p, 0.0), 4) for s in series]} for p in top]},
        "favourite": {"name": fav["player"], "p": fav["p_win"]} if fav else None,
        "next_match": upcoming[0]["date"] if upcoming else ev["start"],
    }


def build(today_iso):
    t = date.fromisoformat(today_iso[:10])
    comps, model = [], {}
    for tour in config.TENNIS_TOURS:
        events = load_tour(tour)
        matches = rated_matches(events, config.GRAND_SLAMS)
        targets = [e for e in events if is_covered(e, tour) and e["end"] and e["start"]
                   and e["end"][:10] >= (t - timedelta(days=30)).isoformat()
                   and e["start"][:10] <= (t + timedelta(days=45)).isoformat()]
        wanted = set()
        for ev in targets:
            for _, ms in main_draw(ev):
                for m in ms:
                    if m["date"]:
                        wanted.add(day(m["date"]))
                        wanted.add((date.fromisoformat(day(m["date"])) - timedelta(days=1)).isoformat())
        elo = TennisElo()
        snaps = elo.run(matches, wanted)

        # backtest: pre-match favourite vs result over the last year
        cut = (t - timedelta(days=365)).isoformat()
        n = acc = brier = ll = 0
        for m in matches:
            if m["date"] >= cut:
                ra, rb = elo.pre[m["id"]]
                p = win_prob(ra, rb)
                y = 1 if m["w"] == 0 else 0
                n += 1
                acc += 1 if (p >= 0.5) == (y == 1) else 0
                brier += (p - y) ** 2
                ll += -math.log(max(p if y else 1 - p, 1e-9))
        model[tour] = {"matches_rated": len(matches), "players": len(elo.ratings),
                       "backtest": {"n": n, "accuracy": acc / n if n else None, "brier": brier / n if n else None,
                                    "log_loss": ll / n if n else None}}
        for ev in targets:
            print("  simulating %s %s" % (tour.upper(), ev["name"]))
            comps.append(event_payload(ev, tour, elo, snaps, today_iso))
    return comps, model


def write(comps):
    for c in comps:
        write_json(os.path.join(SITE_DATA_DIR, "tennis", c["id"] + ".json"), c)
