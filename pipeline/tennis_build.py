"""Build tennis predictions: player ratings, title odds per tournament, odds over time."""
import hashlib
import os
from datetime import date, timedelta

from . import config
from .common import SITE_DATA_DIR, calibration, day, now_iso, track_record, write_json
from . import title_backtest as tb
from . import flags, live_log
from .tennis_data import FAILED_DAYS, fetch_rankings, load_tour
from .tennis_model import (TennisElo, as_of, as_of_rr, best_of_five, fit_surface_weight, is_group_match,
                           main_draw, rated_matches, rr_groups, score, simulate_draw, simulate_finals,
                           surface_of, win_prob)


def seed_for(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def is_covered(ev, tour):
    name = (ev["name"] or "").lower()
    if any(k.lower() in name for k in config.TENNIS_EXCLUDE):
        return False
    return any(k.lower() in name for k in config.TENNIS_TOURS[tour]["keywords"])


def is_finals(ev):
    return any(k.lower() in (ev["name"] or "").lower() for k in config.TENNIS_FINALS)


def has_groups(ev):
    return any(is_group_match(m) and m["a"] and m["b"] for m in ev["matches"])


def is_slam(ev):
    return any(s in (ev["name"] or "") for s in config.GRAND_SLAMS)


def h2h_index(matches):
    """{frozenset(player, player): meetings, newest first}."""
    out = {}
    for m in matches:
        out.setdefault(frozenset((m["a"], m["b"])), []).append(m)
    for v in out.values():
        v.sort(key=lambda m: m["date"] or "", reverse=True)
    return out


def event_payload(ev, tour, elo, snaps, today_iso, projected_field=None, h2h=None, event_names=None):
    rounds = main_draw(ev)
    finals = is_finals(ev)
    projected = None
    if finals and not has_groups(ev) and projected_field:
        projected = [p for p, _ in projected_field]
    bo5 = tour == "atp" and is_slam(ev)
    surface = surface_of(ev["name"], config.TENNIS_SURFACES)
    ratings = elo.ratings_for(surface)  # each player's blend of overall and this-surface rating
    players = {}
    for _, ms in rounds:
        for m in ms:
            for slot in ("a", "b"):
                if m[slot]:
                    players[m[slot]] = m[slot + "n"]
    if projected:
        players.update(dict(projected_field))
    flag = {}  # player id -> flag emoji
    for _, ms in rounds:
        for m in ms:
            for slot in ("a", "b"):
                if m[slot] and m.get(slot + "c"):
                    flag[m[slot]] = flags.for_code(m[slot + "c"])
    finished = [m for _, ms in rounds for m in ms if m["status"] in ("final", "retired", "walkover")]
    final_round = rounds[-1][1] if rounds else []
    champion = None
    if final_round and final_round[0]["status"] in ("final", "retired", "walkover") and final_round[0]["w"] is not None:
        f = final_round[0]
        champion = f["a"] if f["w"] == 0 else f["b"]

    seed = seed_for(ev["id"], today_iso[:10])
    p_sf = {}
    if finals:
        flat = [m for _, ms in rounds for m in ms]
        now, p_sf = simulate_finals(flat, ratings, config.SIMS_TODAY, seed, projected) if (flat or projected) else ({}, {})
    else:
        now = simulate_draw(rounds, ratings, bo5, config.SIMS_TODAY, seed) if rounds else {}

    series_days, series = [], []
    if rounds and not projected:
        days = sorted({day(m["date"]) for m in finished if day(m["date"]) < today_iso[:10]})
        first = min((day(m["date"]) for _, ms in rounds for m in ms if m["date"]), default=None)
        if first:
            pre = (date.fromisoformat(first) - timedelta(days=1)).isoformat()
            for d in [pre] + days:
                if d not in snaps:
                    continue
                past = elo.blend_snapshot(snaps[d], surface)
                if finals:
                    series.append(simulate_finals(as_of_rr(ev, d), past, config.SIMS_REPLAY, seed_for(ev["id"], d))[0])
                else:
                    series.append(simulate_draw(as_of(ev, d), past, bo5, config.SIMS_REPLAY, seed_for(ev["id"], d)))
                series_days.append(d)
    if now:
        series_days.append(today_iso[:10])
        series.append(now)

    lost = set()
    for m in finished:
        if m["w"] is not None and m["a"] and m["b"]:
            lost.add(m["b"] if m["w"] == 0 else m["a"])
    group_of, record = {}, {}
    if finals:
        # a group-stage loss doesn't knock anyone out: still in = can still win the title
        lost = {p for p in players if now.get(p, 0.0) == 0.0 and p != champion}
        comps = rr_groups([m for _, ms in rounds for m in ms])
        if len(comps) == 2:
            group_of = {p: "Group " + "AB"[i] for i, g in enumerate(comps) for p in g}
        for m in finished:
            if is_group_match(m) and m["w"] is not None and m["a"] and m["b"]:
                w, l = (m["a"], m["b"]) if m["w"] == 0 else (m["b"], m["a"])
                record.setdefault(w, [0, 0])[0] += 1
                record.setdefault(l, [0, 0])[1] += 1
    rows = []
    for p in players:
        row = {"player": players[p], "id": p, "rating": round(ratings.get(p, 1500)), "flag": flag.get(p),
               "p_win": round(now.get(p, 0.0), 4), "alive": p not in lost}
        if finals:
            row.update({"p_sf": round(p_sf.get(p, 0.0), 4), "group": group_of.get(p),
                        "record": "%d–%d" % tuple(record.get(p, [0, 0]))})
        rows.append(row)
    rows.sort(key=lambda r: (-r["p_win"], not r["alive"], -r["rating"]))

    def p_match(a, b):
        p = win_prob(ratings.get(a, 1500), ratings.get(b, 1500))
        return best_of_five(p) if bo5 else p

    upcoming = []
    for name, ms in rounds:
        for m in sorted(ms, key=lambda m: m["date"] or ""):
            if m["status"] in ("scheduled", "live") and m["a"] and m["b"]:
                upcoming.append({"date": m["date"], "round": name, "a": m["an"], "b": m["bn"],
                                 "af": flag.get(m["a"]), "bf": flag.get(m["b"]),
                                 "p": round(p_match(m["a"], m["b"]), 3), "live": m["status"] == "live",
                                 "r": [round(ratings.get(m["a"], 1500)), round(ratings.get(m["b"], 1500))],
                                 "h2h": [{"date": x["date"], "event": (event_names or {}).get(x.get("event"), ""),
                                          "round": x["round"], "winner": x["an"] if x["w"] == 0 else x["bn"]}
                                         for x in (h2h or {}).get(frozenset((m["a"], m["b"])), [])[:5]]})
    calls = []  # every finished match in this event, judged against its pre-match prediction
    for m in finished:
        if m["id"] in elo.pre and m["w"] is not None:
            p = win_prob(*elo.pre_rating(m["id"]))
            p = best_of_five(p) if bo5 else p
            calls.append(((p >= 0.5) == (m["w"] == 0), (p - (m["w"] == 0)) ** 2))

    recent = []
    for m in sorted(finished, key=lambda m: (m["date"] or "", m["id"]), reverse=True)[:12]:
        if m["id"] in elo.pre and m["w"] is not None:
            ra, rb = elo.pre_rating(m["id"])
            p = win_prob(ra, rb)
            p = best_of_five(p) if bo5 else p
            recent.append({"date": m["date"], "round": m["round"], "a": m["an"], "b": m["bn"], "w": m["w"],
                           "af": flag.get(m["a"]), "bf": flag.get(m["b"]),
                           "p": round(p, 3), "called": (p >= 0.5) == (m["w"] == 0)})

    top = sorted({p for s in series for p in s}, key=lambda p: -max(s.get(p, 0) for s in series))[:8]
    top.sort(key=lambda p: (-series[0].get(p, 0), players.get(p, p)))  # colours stay with each player
    t = today_iso[:10]
    if champion:
        status = "finished"
    elif not rounds or projected or (ev["start"] or "")[:10] > t:
        status = "upcoming"
    else:
        status = "live"
    fav = rows[0] if rows and rows[0]["p_win"] > 0 else None
    return {
        "id": ev["id"], "sport": "tennis", "tour": config.TENNIS_TOURS[tour]["name"], "name": ev["name"],
        "group": tour + ("-finals" if finals else "-slam" if is_slam(ev) else "-1000"),
        "format": "finals" if finals else "knockout", "projected": bool(projected),
        "start": ev["start"], "end": ev["end"],
        "slam": is_slam(ev), "surface": surface, "best_of": 5 if bo5 else 3, "updated": now_iso(), "status": status,
        "defending": ev.get("defending"), "champion": players.get(champion) if champion else None,
        "table": rows, "upcoming": upcoming[:30], "recent": recent, "record": track_record(calls),
        "history": {"dates": series_days,
                    "series": [{"team": players.get(p, p), "p": [round(s.get(p, 0.0), 4) for s in series]} for p in top]},
        "favourite": {"name": fav["player"], "p": fav["p_win"]} if fav else None,
        "next_match": upcoming[0]["date"] if upcoming else ev["start"],
    }


def champion_of(ev):
    rounds = main_draw(ev)
    if not rounds or not rounds[-1][1]:
        return None
    f = rounds[-1][1][0]
    if f["status"] not in ("final", "retired", "walkover") or f["w"] is None:
        return None
    return f["a"] if f["w"] == 0 else f["b"]


def past_events(events, tour, t, warmup_days=150):
    """Finished covered events after the ratings' warm-up, with a known champion."""
    start_ok = (date.fromisoformat(config.TENNIS_HISTORY_FROM) + timedelta(days=warmup_days)).isoformat()
    done = (t - timedelta(days=2)).isoformat()
    return [ev for ev in events if is_covered(ev, tour) and ev.get("start") and ev.get("end")
            and ev["start"][:10] >= start_ok and ev["end"][:10] < done and champion_of(ev)
            and len([m for _, ms in main_draw(ev) for m in ms]) >= 7]


def grade_past_events(past, tour, elo, snaps, n=1000):
    rows = []
    for ev in past:
        flat = [m for _, ms in main_draw(ev) for m in ms]
        d = tb.pre_day(flat)
        if d not in snaps:
            continue
        surface = surface_of(ev["name"], config.TENNIS_SURFACES)
        ratings = elo.blend_snapshot(snaps[d], surface)
        seed = seed_for("bt", ev["id"])
        if is_finals(ev):
            odds = simulate_finals(as_of_rr(ev, d), ratings, n, seed)[0]
        else:
            odds = simulate_draw(as_of(ev, d), ratings, tour == "atp" and is_slam(ev), n, seed)
        names = {}
        for m in flat:
            for slot in ("a", "b"):
                if m[slot]:
                    names[m[slot]] = m[slot + "n"]
        rows.append(tb.grade(ev["name"], ev["start"][:4], odds, champion_of(ev), names))
    return rows


def build(today_iso):
    t = date.fromisoformat(today_iso[:10])
    comps, model = [], {}
    for tour in config.TENNIS_TOURS:
        events = load_tour(tour)
        matches = rated_matches(events, config.GRAND_SLAMS, config.TENNIS_SURFACES)
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
        past = past_events(events, tour, t)
        wanted.update(tb.pre_day([m for _, ms in main_draw(ev) for m in ms]) for ev in past)
        elo = TennisElo()
        snaps = elo.run(matches, wanted)

        # fit the overall/surface blend on the last year, and report both for comparison
        cut = (t - timedelta(days=365)).isoformat()
        recent = [m for m in matches if m["date"] >= cut]
        elo.weight = fit_surface_weight(elo, recent)
        by_surface = {}
        for m in matches:
            by_surface[m["surface"]] = by_surface.get(m["surface"], 0) + 1
        model[tour] = {"matches_rated": len(matches), "players": len(elo.ratings), "surface_weight": elo.weight,
                       "matches_by_surface": by_surface,
                       "backtest": score(elo, recent, elo.weight),
                       "backtest_overall_only": score(elo, recent, 0.0),
                       "calibration": calibration(
                           [pair for m in recent for pr in [win_prob(*elo.pre_rating(m["id"]))]
                            for pair in ((pr, int(m["w"] == 0)), (1 - pr, int(m["w"] == 1)))])}
        graded = grade_past_events(past, tour, elo, snaps)
        model[tour]["title_backtest"] = {"summary": tb.summarise(graded), "events": graded}
        # for team pages and the compare tool: rating history (last year) and every rating by surface
        since = (t - timedelta(days=365)).isoformat()
        hist = {}
        for m in matches:
            if m["date"] >= since and m["id"] in elo.pre:
                oa, ob, _, _ = elo.pre[m["id"]]
                hist.setdefault(m["an"], []).append([day(m["date"]), round(oa)])
                hist.setdefault(m["bn"], []).append([day(m["date"]), round(ob)])
        for p, r in elo.ratings.items():
            if elo.names.get(p) in hist:
                hist[elo.names[p]].append([today_iso[:10], round(r)])
        top = sorted(elo.ratings, key=lambda p: -elo.ratings[p])[:300]
        model[tour]["_histories"] = hist
        model[tour]["_ratings"] = {elo.names.get(p, p): [round(elo.ratings[p])] + [round(elo.surf[s].get(p, elo.init)) for s in ("hard", "clay", "grass")]
                                   for p in top}
        pair_index = h2h_index(matches)
        event_names = {e["id"]: e["name"] for e in events}
        field = None
        if any(is_finals(ev) and not has_groups(ev) for ev in targets):
            try:
                field = fetch_rankings(tour, 8)
            except RuntimeError as err:
                print("  ! %s rankings: %s" % (tour, err))
        for ev in targets:
            lo = (date.fromisoformat(ev["start"][:10]) - timedelta(days=3)).isoformat()
            if any(tr == tour and lo <= d <= ev["end"][:10] for tr, d in FAILED_DAYS):
                old = live_log.stale_copy("tennis", ev["id"], "ESPN didn't answer for part of this draw")
                if old:
                    print("  ! %s: fetch failed, keeping the last good copy" % ev["name"])
                    comps.append(old)
                    continue
            print("  simulating %s %s" % (tour.upper(), ev["name"]))
            comps.append(event_payload(ev, tour, elo, snaps, today_iso, field, pair_index, event_names))
    return comps, model


def write(comps):
    for c in comps:
        write_json(os.path.join(SITE_DATA_DIR, "tennis", c["id"] + ".json"), c)
