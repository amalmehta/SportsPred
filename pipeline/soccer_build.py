"""Build soccer predictions: ratings from history, today's odds, and odds-over-time replays."""
import hashlib
import os
from datetime import date, timedelta

import numpy as np

from . import config
from .common import SITE_DATA_DIR, day, now_iso, today, write_json
from .soccer_data import fetch_groups, load_international_results, load_slug
from .soccer_model import Elo, fit_goals_model, score_predictions
from .soccer_sim import (Matchups, simulate_groups_ko, simulate_league,
                         simulate_league_phase_ko)

GROUP_STAGES = ("league", "group")
INTL_K = [  # (substring of tournament name, K multiplier)
    ("FIFA World Cup qualification", 2.0), ("FIFA World Cup", 3.0), ("UEFA Euro qualification", 2.0),
    ("UEFA Euro", 2.5), ("Nations League", 1.75), ("Copa América", 2.5), ("African Cup of Nations", 2.25),
    ("AFC Asian Cup", 2.25), ("Gold Cup", 2.0), ("Friendly", 1.0),
]


def seed_for(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def outcome(m):
    return 0 if m["hg"] > m["ag"] else (1 if m["hg"] == m["ag"] else 2)


# ---------------------------------------------------------------- ratings

def club_matches(today_):
    slugs = [c["slug"] for c in config.SOCCER_COMPETITIONS] + config.SOCCER_RATING_ONLY
    by_slug = {}
    for s in slugs:
        print("  soccer: %s" % s)
        ms = load_slug(s, config.SOCCER_HISTORY_FROM, today_.year + 1)
        for m in ms:
            m["home_key"], m["away_key"] = m["home_id"], m["away_id"]
        by_slug[s] = ms
    return by_slug


def make_club_elo(hfa):
    league_teams = {}

    def new_team(team, m, elo):
        # a club first seen in a domestic league that already has rated clubs is most likely
        # newly promoted: start it near the bottom of that league
        slug = (m or {}).get("slug", "")
        rated = [elo.ratings[t] for t in league_teams.get(slug, ()) if t in elo.ratings]
        if slug.split(".")[-1] == "1" and len(rated) >= 10:
            return float(np.percentile(rated, 15))
        return elo.init

    elo = Elo(k=20.0, hfa=hfa, new_team_rating=new_team)
    return elo, league_teams


def run_club_elo(finished, hfa, snapshot_days=(), collect_from="2022-07-01"):
    elo, league_teams = make_club_elo(hfa)
    samples = []

    def on_match(m, rh, ra):
        league_teams.setdefault(m["slug"], set()).update((m["home"], m["away"]))
        if m["date"] >= collect_from:
            samples.append((rh + (0 if m["neutral"] else hfa) - ra, m["hg"], m["ag"]))

    rows = [dict(m, home=m["home_key"], away=m["away_key"]) for m in finished]
    snaps = elo.run(rows, snapshot_days, on_match)
    return elo, samples, snaps


def outcome_loglik(samples, gm):
    ll = 0.0
    for gap, hg, ag in samples:
        p = gm.outcome_probs(gap)[:3]
        o = 0 if hg > ag else (1 if hg == ag else 2)
        ll += np.log(max(p[o], 1e-9))
    return ll


def fit_hfa(finished, grid=(40, 60, 80, 100)):
    best = None
    for hfa in grid:
        _, samples, _ = run_club_elo(finished, hfa)
        gm = fit_goals_model(samples)
        ll = outcome_loglik(samples[-6000:], gm)
        if best is None or ll > best[0]:
            best = (ll, hfa, gm)
    return best[1], best[2]


# ---------------------------------------------------------------- seasons

def current_season(matches, today_iso):
    upcoming = [m for m in matches if m["status"] != "final" and m["date"] >= today_iso[:10]]
    if upcoming:
        return min(upcoming, key=lambda m: m["date"])["season"]
    finished = [m for m in matches if m["status"] == "final"]
    return max(finished, key=lambda m: m["date"])["season"] if finished else None


def season_label(matches):
    years = sorted({int(m["date"][:4]) for m in matches})
    if not years:
        return ""
    return str(years[0]) if years[0] == years[-1] else "%d–%s" % (years[0], str(years[-1])[2:])


def as_of(matches, d):
    """Copy of the matches as they stood at the end of day d (later results become fixtures)."""
    out = []
    for m in matches:
        if m["status"] == "final" and day(m["date"]) > d:
            m = dict(m, status="scheduled")
        out.append(m)
    return out


def replay_days(season_matches, today_iso, max_points=60):
    days = sorted({day(m["date"]) for m in season_matches if m["status"] == "final"})
    if not days:
        return []
    first = (date.fromisoformat(days[0]) - timedelta(days=1)).isoformat()
    days = [d for d in days if d < today_iso[:10]]
    if len(days) > max_points:
        step = len(days) / float(max_points)
        days = [days[int(i * step)] for i in range(max_points - 1)] + [days[-1]]
    return [first] + days


# ---------------------------------------------------------------- one competition

def simulate_comp(cfg, season_matches, ratings, gm, hfa, n, seed, groups=None):
    mu = Matchups(ratings, gm, hfa)
    fmt = cfg["format"]
    fin = [m for m in season_matches if m["status"] == "final"]
    todo = [m for m in season_matches if m["status"] != "final"]
    if fmt == "league":
        teams = sorted({m["home_key"] for m in season_matches} | {m["away_key"] for m in season_matches})
        return simulate_league(teams, [(m["home_key"], m["away_key"], m["hg"], m["ag"]) for m in fin],
                               [(m["home_key"], m["away_key"], m["neutral"]) for m in todo], mu, n, seed)
    is_group = lambda m: any(g in m["stage"] for g in GROUP_STAGES) and "relegation" not in m["stage"]
    gs = [m for m in season_matches if is_group(m)]
    start = min((m["date"] for m in gs), default="")
    ko = [m for m in season_matches if not is_group(m) and m["date"] > start and "relegation" not in m["stage"]]
    gs_fin = [(m["home_key"], m["away_key"], m["hg"], m["ag"]) for m in gs if m["status"] == "final"]
    gs_todo = [(m["home_key"], m["away_key"], m["neutral"]) for m in gs if m["status"] != "final"]
    if fmt == "league_phase_ko":
        teams = sorted({m["home_key"] for m in gs} | {m["away_key"] for m in gs})
        return simulate_league_phase_ko(teams, gs_fin, gs_todo, ko, mu, n, seed)
    return simulate_groups_ko(groups, gs_fin, gs_todo, ko, mu, n, seed,
                              advance_top=cfg.get("advance_top", 2), two_leg_min=cfg.get("two_leg_min", 999))


def comp_payload(cfg, sport_group, season_matches, elo, gm, snaps, names, today_iso, groups=None, group_of=None):
    hfa = elo.hfa
    seed = seed_for(cfg["slug"], today_iso[:10])
    now = simulate_comp(cfg, season_matches, elo.ratings, gm, hfa, config.SIMS_TODAY, seed, groups)

    # odds over time: replay the season with only what was known at the end of each match day
    series_days, series = [], []
    for d in replay_days(season_matches, today_iso):
        if d not in snaps:
            continue
        res = simulate_comp(cfg, as_of(season_matches, d), snaps[d], gm, hfa, config.SIMS_REPLAY,
                            seed_for(cfg["slug"], d), groups)
        series_days.append(d)
        series.append(res["p_win"])
    series_days.append(today_iso[:10])
    series.append(now["p_win"])

    fin = [m for m in season_matches if m["status"] == "final"]
    table = {}
    for m in fin:
        if any(s in m["stage"] for s in ("relegation",)):
            continue
        for k, gf, ga in ((m["home_key"], m["hg"], m["ag"]), (m["away_key"], m["ag"], m["hg"])):
            row = table.setdefault(k, {"played": 0, "pts": 0, "gd": 0})
            if cfg["format"] == "league" or any(g in m["stage"] for g in GROUP_STAGES):
                row["played"] += 1
                row["pts"] += 3 if gf > ga else (1 if gf == ga else 0)
                row["gd"] += gf - ga
    teams = sorted(set(now["p_win"]) | set(table), key=lambda t: (-now["p_win"].get(t, 0), -now["proj_pts"].get(t, 0)))
    rows = []
    for t in teams:
        r = table.get(t, {"played": 0, "pts": 0, "gd": 0})
        rows.append({
            "team": names.get(t, t), "rating": round(elo.ratings.get(t, 1400)),
            "played": r["played"], "pts": r["pts"], "gd": r["gd"],
            "proj_pts": round(now["proj_pts"][t], 1) if t in now.get("proj_pts", {}) else None,
            "p_win": round(now["p_win"].get(t, 0.0), 4),
            "group": (group_of or {}).get(t),
        })

    mu = Matchups(elo.ratings, gm, hfa)
    upcoming = []
    todo = sorted([m for m in season_matches if m["status"] != "final"], key=lambda m: m["date"])
    horizon = (date.fromisoformat(today_iso[:10]) + timedelta(days=10)).isoformat()
    for m in todo:
        if m["status"] == "postponed" or (len(upcoming) >= 10 and m["date"] > horizon):
            continue
        if "tbd" in (m["home"] or "").lower() or "tbd" in (m["away"] or "").lower():
            continue
        ph, pd, pa, score, (lh, la) = mu.probs(m["home_key"], m["away_key"], m["neutral"])
        upcoming.append({"date": m["date"], "home": m["home"], "away": m["away"], "live": m["status"] == "live",
                         "p": [round(ph, 3), round(pd, 3), round(pa, 3)], "score": list(score),
                         "xg": [round(lh, 2), round(la, 2)]})
        if len(upcoming) >= 30:
            break

    recent = []
    for m in sorted(fin, key=lambda m: m["date"], reverse=True)[:12]:
        if m["id"] not in elo.pre:
            continue
        rh, ra = elo.pre[m["id"]]
        p = gm.outcome_probs(rh + (0 if m["neutral"] else hfa) - ra)[:3]
        recent.append({"date": m["date"], "home": m["home"], "away": m["away"], "hg": m["hg"], "ag": m["ag"],
                       "p": [round(x, 3) for x in p],
                       "called": max(range(3), key=lambda i: p[i]) == outcome(m)})

    top = sorted({t for s in series for t in s}, key=lambda t: -max(s.get(t, 0) for s in series))[:8]
    fav = rows[0] if rows else None
    finished_all = not todo
    return {
        "id": cfg["slug"], "sport": "soccer", "name": cfg["name"], "group": sport_group,
        "country": cfg.get("country", ""), "format": cfg["format"], "season": season_label(season_matches),
        "updated": now_iso(), "status": "finished" if finished_all else ("live" if fin else "upcoming"),
        "table": rows, "upcoming": upcoming, "recent": recent,
        "history": {"dates": series_days,
                    "series": [{"team": names.get(t, t), "p": [round(s.get(t, 0.0), 4) for s in series]} for t in top]},
        "favourite": {"name": fav["team"], "p": fav["p_win"]} if fav else None,
        "next_match": upcoming[0]["date"] if upcoming else None,
    }


# ---------------------------------------------------------------- entry points

def build_clubs(today_iso):
    t = date.fromisoformat(today_iso[:10])
    by_slug = club_matches(t)
    all_matches = sorted([m for ms in by_slug.values() for m in ms], key=lambda m: m["date"])
    finished = [m for m in all_matches if m["status"] == "final"]
    names = {m["home_key"]: m["home"] for m in all_matches}
    names.update({m["away_key"]: m["away"] for m in all_matches})

    print("  fitting home advantage + goals model")
    hfa, gm = fit_hfa(finished)

    seasons, wanted = {}, set()
    for cfg in config.SOCCER_COMPETITIONS:
        ms = by_slug[cfg["slug"]]
        s = current_season(ms, today_iso)
        sm = [m for m in ms if m["season"] == s]
        if cfg["format"] == "league_phase_ko":  # drop qualifying rounds
            lp = [m["date"] for m in sm if "league" in m["stage"]]
            sm = [m for m in sm if lp and m["date"] >= min(lp)]
        seasons[cfg["slug"]] = sm
        wanted.update(replay_days(sm, today_iso))
    elo, samples, snaps = run_club_elo(finished, hfa, wanted)

    comps, rows = [], []
    cut = (t - timedelta(days=365)).isoformat()
    predicted = {c["slug"] for c in config.SOCCER_COMPETITIONS}
    for m in finished:
        if m["slug"] in predicted and m["date"] >= cut and m["id"] in elo.pre:
            rh, ra = elo.pre[m["id"]]
            p = gm.outcome_probs(rh + (0 if m["neutral"] else hfa) - ra)[:3]
            rows.append((p[0], p[1], p[2], outcome(m)))
    for cfg in config.SOCCER_COMPETITIONS:
        print("  simulating %s" % cfg["name"])
        payload = comp_payload(cfg, cfg["group"], seasons[cfg["slug"]], elo, gm, snaps, names, today_iso)
        comps.append(payload)
    model = {"hfa": hfa, "goals_base": round(float(np.exp(gm.base)), 3), "slope": round(gm.slope, 3),
             "backtest": score_predictions(rows), "matches_rated": len(finished)}
    return comps, model


def intl_key(name):
    return config.COUNTRY_ALIASES.get(name, name)


def build_international(today_iso):
    t = date.fromisoformat(today_iso[:10])
    archive = load_international_results()
    last = max(r["date"] for r in archive)
    k_mult = lambda tour: next((k for s, k in INTL_K if s in tour), 1.5)
    rows = [{"id": "a%d" % i, "date": r["date"], "home": r["home"], "away": r["away"], "hg": r["hg"], "ag": r["ag"],
             "neutral": r["neutral"], "k_mult": k_mult(r["tournament"])} for i, r in enumerate(archive)]

    active = []
    for cfg in config.INTERNATIONAL_COMPETITIONS:
        try:
            ms = load_slug(cfg["slug"], t.year - 1, t.year + 1)
        except RuntimeError:
            continue
        for m in ms:
            m["home_key"], m["away_key"] = intl_key(m["home"]), intl_key(m["away"])
        soon = (t + timedelta(days=300)).isoformat()
        recent = (t - timedelta(days=10)).isoformat()
        live = [m for m in ms if (m["status"] != "final" and today_iso[:10] <= m["date"][:10] <= soon)
                or (m["status"] == "final" and m["date"] >= recent)]
        if not live:
            continue
        s = current_season(ms, today_iso)
        sm = [m for m in ms if m["season"] == s]
        active.append((cfg, sm))
        # results newer than the archive feed the ratings too
        for m in ms:
            if m["status"] == "final" and m["date"][:10] > last:
                rows.append({"id": m["id"], "date": m["date"], "home": m["home_key"], "away": m["away_key"],
                             "hg": m["hg"], "ag": m["ag"], "neutral": m["neutral"], "k_mult": 1.75})
    rows.sort(key=lambda r: r["date"])

    hfa = 100.0
    wanted = set()
    for cfg, sm in active:
        wanted.update(replay_days(sm, today_iso))
    elo = Elo(k=20.0, hfa=hfa, init=1300.0)
    samples = []

    def on_match(m, rh, ra):
        if m["date"] >= "2014-01-01":
            samples.append((rh + (0 if m["neutral"] else hfa) - ra, m["hg"], m["ag"]))
    snaps = elo.run(rows, wanted, on_match)
    gm = fit_goals_model(samples)

    comps = []
    for cfg, sm in active:
        print("  simulating %s" % cfg["name"])
        names = {m["home_key"]: m["home"] for m in sm}
        names.update({m["away_key"]: m["away"] for m in sm})
        id_to_key = {m["home_id"]: m["home_key"] for m in sm}
        id_to_key.update({m["away_id"]: m["away_key"] for m in sm})
        raw = fetch_groups(cfg["slug"])
        flt = cfg.get("group_filter", "")
        groups = {g: [id_to_key[i] for i in ids if i in id_to_key] for g, ids in raw.items() if g.startswith(flt)}
        groups = {g: v for g, v in groups.items() if len(v) >= 2}
        if not groups:
            continue
        keep = {t for v in groups.values() for t in v}
        group_of = {t: g for g, v in groups.items() for t in v}
        sm_kept = [m for m in sm if m["home_key"] in keep or m["away_key"] in keep]
        comps.append(comp_payload(cfg, cfg["group"], sm_kept, elo, gm, snaps, names, today_iso, groups, group_of))

    cut = (t - timedelta(days=365)).isoformat()
    bt = []
    for r in rows:
        if r["date"] >= cut and r["id"] in elo.pre:
            rh, ra = elo.pre[r["id"]]
            p = gm.outcome_probs(rh + (0 if r["neutral"] else hfa) - ra)[:3]
            bt.append((p[0], p[1], p[2], outcome(r)))
    model = {"hfa": hfa, "goals_base": round(float(np.exp(gm.base)), 3), "slope": round(gm.slope, 3),
             "backtest": score_predictions(bt), "matches_rated": len(rows)}
    return comps, model


def write(comps):
    for c in comps:
        write_json(os.path.join(SITE_DATA_DIR, "soccer", c["id"] + ".json"), c)
