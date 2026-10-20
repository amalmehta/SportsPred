"""Build soccer predictions: ratings from history, today's odds, and odds-over-time replays."""
import hashlib
import os
from datetime import date, timedelta

import numpy as np

from . import config
from .common import SITE_DATA_DIR, calibration, day, now_iso, today, track_record, write_json
from . import flags, live_log
from .soccer_data import FAILED, fetch_groups, load_international_results, load_slug
from .soccer_model import Elo, fit_goals_model, score_predictions
from . import title_backtest as tb
from .soccer_sim import RATING_SD
from .soccer_sim import (Matchups, simulate_groups_ko, simulate_league,
                         simulate_league_phase_ko, simulate_qualifying)

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


# How far a whole league moves when one of its clubs beats (or loses to) a club from another league
# in Europe. Domestic games can't tell leagues apart, so this is the only way league strength is
# learned. Backtested Oct 2026: European log loss 0.978 -> 0.955 (latest 2 seasons), 0.993 -> 0.970
# (2 seasons before), with domestic predictions slightly better too.
LEAGUE_SHIFT = 16.0


def run_club_elo(finished, hfa, snapshot_days=(), collect_from="2022-07-01", league_shift=LEAGUE_SHIFT):
    elo, league_teams = make_club_elo(hfa)
    samples = []
    league_of, members = {}, {}  # club -> its domestic league, league -> clubs

    def shift_league(league, delta):
        for team in members.get(league, ()):
            if team in elo.ratings:
                elo.ratings[team] += delta

    def on_match(m, rh, ra):
        league_teams.setdefault(m["slug"], set()).update((m["home"], m["away"]))
        gap = rh + (0 if m["neutral"] else hfa) - ra
        if m["date"] >= collect_from:
            samples.append((gap, m["hg"], m["ag"]))
        if m["slug"].endswith(".1"):  # a domestic league game: remember where each club plays
            for team in (m["home"], m["away"]):
                old = league_of.get(team)
                if old != m["slug"]:
                    if old:
                        members[old].discard(team)
                    league_of[team] = m["slug"]
                    members.setdefault(m["slug"], set()).add(team)
        elif league_shift and m["slug"].startswith("uefa."):
            lh, la = league_of.get(m["home"]), league_of.get(m["away"])
            if lh and la and lh != la:
                expected = 1.0 / (1.0 + 10 ** (-gap / 400.0))
                actual = 1.0 if m["hg"] > m["ag"] else (0.5 if m["hg"] == m["ag"] else 0.0)
                shift_league(lh, league_shift * (actual - expected))
                shift_league(la, -league_shift * (actual - expected))

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

def simulate_comp(cfg, season_matches, ratings, gm, hfa, n, seed, groups=None, track=0):
    mu = Matchups(ratings, gm, hfa)
    fmt = cfg["format"]
    fin = [m for m in season_matches if m["status"] == "final"]
    todo = [m for m in season_matches if m["status"] != "final"]
    if fmt == "league":
        teams = sorted({m["home_key"] for m in season_matches} | {m["away_key"] for m in season_matches})
        return simulate_league(teams, [(m["home_key"], m["away_key"], m["hg"], m["ag"]) for m in fin],
                               [(m["home_key"], m["away_key"], m["neutral"]) for m in todo], mu, n, seed,
                               top=cfg.get("top"), bottom=cfg.get("drop"), track=track)
    if fmt == "qualifying":
        direct, nxt, _ = cfg["_slots"]
        return simulate_qualifying(groups, [(m["home_key"], m["away_key"], m["hg"], m["ag"]) for m in fin],
                                   [(m["home_key"], m["away_key"], m["neutral"]) for m in todo], mu, n, seed,
                                   direct, nxt)
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


def rating_histories(finished, elo, names, today_iso, days):
    """{team name: [[date, rating before that match], ..., [today, rating now]]} for the team pages."""
    since = (date.fromisoformat(today_iso[:10]) - timedelta(days=days)).isoformat()
    out = {}
    for m in finished:
        if m["date"] < since or m.get("id") not in elo.pre:
            continue
        for key, r in zip((m["home_key"], m["away_key"]), elo.pre[m["id"]]):
            if key in names:
                out.setdefault(names[key], []).append([day(m["date"]), round(r)])
    for key, name in names.items():
        if name in out and key in elo.ratings:
            out[name].append([today_iso[:10], round(elo.ratings[key])])
    return out


def h2h_index(finished):
    """{frozenset(team, team): meetings, newest first} for head-to-head records."""
    out = {}
    for m in finished:
        out.setdefault(frozenset((m["home_key"], m["away_key"])), []).append(m)
    for v in out.values():
        v.sort(key=lambda m: m["date"], reverse=True)
    return out


def meetings(h2h, a, b, names, keep=5):
    return [{"date": m["date"], "home": names.get(m["home_key"], m["home_key"]), "away": names.get(m["away_key"], m["away_key"]),
             "hg": m["hg"], "ag": m["ag"]} for m in (h2h or {}).get(frozenset((a, b)), [])[:keep]]


def whatif_data(season_matches, mu, names, cfg):
    """Everything the page needs to re-run the league itself: table so far and every remaining fixture's
    expected goals (the what-if tool picks results and simulates the rest in the browser)."""
    teams = sorted({m["home_key"] for m in season_matches} | {m["away_key"] for m in season_matches})
    idx = {t: i for i, t in enumerate(teams)}
    base = {t: [0, 0, 0] for t in teams}
    fixtures = []
    for m in sorted(season_matches, key=lambda m: m["date"]):
        if m["status"] == "final":
            for t, gf, ga in ((m["home_key"], m["hg"], m["ag"]), (m["away_key"], m["ag"], m["hg"])):
                base[t][0] += 3 if gf > ga else (1 if gf == ga else 0)
                base[t][1] += gf - ga
                base[t][2] += gf
        else:
            lh, la = mu.lambdas(m["home_key"], m["away_key"], m["neutral"])
            fixtures.append([idx[m["home_key"]], idx[m["away_key"]], round(lh, 3), round(la, 3), m["date"]])
    return {"teams": [names.get(t, t) for t in teams], "base": [base[t] for t in teams], "fixtures": fixtures,
            "noise": round(RATING_SD * mu.gm.slope / 400.0, 4), "top": cfg.get("top"), "drop": cfg.get("drop")}


def comp_payload(cfg, sport_group, season_matches, elo, gm, snaps, names, today_iso, groups=None, group_of=None, h2h=None):
    hfa = elo.hfa
    seed = seed_for(cfg["slug"], today_iso[:10])
    now = simulate_comp(cfg, season_matches, elo.ratings, gm, hfa, config.SIMS_TODAY, seed, groups,
                        track=15 if cfg["format"] == "league" else 0)
    qualifying = cfg["format"] == "qualifying"
    key = "p_qualify" if qualifying else "p_win"  # what the chart and the headline track

    # odds over time: replay the season with only what was known at the end of each match day
    series_days, series = [], []
    for d in replay_days(season_matches, today_iso):
        if d not in snaps:
            continue
        res = simulate_comp(cfg, as_of(season_matches, d), snaps[d], gm, hfa, config.SIMS_REPLAY,
                            seed_for(cfg["slug"], d), groups)
        series_days.append(d)
        series.append(res[key])
    series_days.append(today_iso[:10])
    series.append(now[key])

    fin = [m for m in season_matches if m["status"] == "final"]
    table = {}
    for m in fin:
        if any(s in m["stage"] for s in ("relegation",)):
            continue
        for k, gf, ga in ((m["home_key"], m["hg"], m["ag"]), (m["away_key"], m["ag"], m["hg"])):
            row = table.setdefault(k, {"played": 0, "pts": 0, "gd": 0})
            if cfg["format"] in ("league", "qualifying") or any(g in m["stage"] for g in GROUP_STAGES):
                row["played"] += 1
                row["pts"] += 3 if gf > ga else (1 if gf == ga else 0)
                row["gd"] += gf - ga
    teams = sorted(set(now["p_win"]) | set(table), key=lambda t: (-now["p_win"].get(t, 0), -now["proj_pts"].get(t, 0)))
    if qualifying:  # group by group, likeliest qualifiers first
        teams = [t for t in teams if t in now["p_win"]]
        teams.sort(key=lambda t: ((group_of or {}).get(t) or "", -now["p_qualify"][t], -now["proj_pts"][t]))
    national = sport_group in ("international", "qualifying")
    flag = (lambda key: flags.for_country(key)) if national else (lambda key: None)
    rows = []
    for t in teams:
        r = table.get(t, {"played": 0, "pts": 0, "gd": 0})
        rows.append({
            "team": names.get(t, t), "rating": round(elo.ratings.get(t, 1400)),
            "played": r["played"], "pts": r["pts"], "gd": r["gd"],
            "proj_pts": round(now["proj_pts"][t], 1) if t in now.get("proj_pts", {}) else None,
            "p_win": round(now["p_win"].get(t, 0.0), 4),
            "group": (group_of or {}).get(t), "flag": flag(t),
        })
        if qualifying:
            rows[-1].update({"p_qualify": round(now["p_qualify"][t], 4), "p_playoff": round(now["p_playoff"][t], 4)})
        for k in ("p_top", "p_drop", "p_ko"):  # top-4 / relegation, or UEFA top-8 / knockouts
            if k in now:
                rows[-1][k] = round(now[k].get(t, 0.0), 4)

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
                         "hf": flag(m["home_key"]), "af": flag(m["away_key"]),
                         "p": [round(ph, 3), round(pd, 3), round(pa, 3)], "score": list(score),
                         "xg": [round(lh, 2), round(la, 2)], "neutral": m["neutral"],
                         "r": [round(mu.rating(m["home_key"])), round(mu.rating(m["away_key"]))],
                         "h2h": meetings(h2h, m["home_key"], m["away_key"], names)})
        if len(upcoming) >= 30:
            break

    calls = []  # every finished match this season, judged against its pre-match prediction
    for m in fin:
        if m["id"] in elo.pre:
            rh, ra = elo.pre[m["id"]]
            p = gm.outcome_probs(rh + (0 if m["neutral"] else hfa) - ra)[:3]
            o = outcome(m)
            calls.append((max(range(3), key=lambda i: p[i]) == o, sum((p[i] - (i == o)) ** 2 for i in range(3))))

    recent = []
    for m in sorted(fin, key=lambda m: m["date"], reverse=True)[:12]:
        if m["id"] not in elo.pre:
            continue
        rh, ra = elo.pre[m["id"]]
        p = gm.outcome_probs(rh + (0 if m["neutral"] else hfa) - ra)[:3]
        recent.append({"date": m["date"], "home": m["home"], "away": m["away"], "hg": m["hg"], "ag": m["ag"],
                       "hf": flag(m["home_key"]), "af": flag(m["away_key"]),
                       "p": [round(x, 3) for x in p],
                       "called": max(range(3), key=lambda i: p[i]) == outcome(m)})

    if qualifying:  # the races that moved most, not the certainties
        spread = lambda t: max(s.get(t, 0) for s in series) - min(s.get(t, 0) for s in series)
        top = sorted({t for s in series for t in s}, key=lambda t: -spread(t))[:8]
        fav = max(rows, key=lambda r: (r["p_qualify"], r["p_win"])) if rows else None
    else:
        top = sorted({t for s in series for t in s}, key=lambda t: -max(s.get(t, 0) for s in series))[:8]
        fav = rows[0] if rows else None
    # chart colours go by series order: order by the first point (fixed all season), not today's rank,
    # so a team keeps its colour as the race changes
    top.sort(key=lambda t: (-series[0].get(t, 0), names.get(t, t)))
    finished_all = not todo
    return {
        "id": cfg["slug"], "sport": "soccer", "name": cfg["name"], "group": sport_group,
        "country": cfg.get("country", ""), "format": cfg["format"], "season": season_label(season_matches),
        "updated": now_iso(), "status": "finished" if finished_all else ("live" if fin else "upcoming"),
        "table": rows, "upcoming": upcoming, "recent": recent,
        "history": {"dates": series_days,
                    "series": [{"team": names.get(t, t), "p": [round(s.get(t, 0.0), 4) for s in series]} for t in top]},
        "favourite": {"name": fav["team"], "p": fav[key]} if fav else None,
        "next_match": upcoming[0]["date"] if upcoming else None,
        "record": track_record(calls),
        "hfa": hfa,
        "swings": [dict(sw, home=names.get(sw["home_key"], sw["home_key"]), away=names.get(sw["away_key"], sw["away_key"]),
                        date=next((m["date"] for m in todo if m["home_key"] == sw["home_key"] and m["away_key"] == sw["away_key"]), None),
                        **{"if": {names.get(k, k): v for k, v in sw["if"].items()}})
                   for sw in now.get("swings", [])],
        "whatif": whatif_data(season_matches, mu, names, cfg) if cfg["format"] == "league" else None,
        "places": ({"top": cfg.get("top"), "drop": cfg.get("drop")} if cfg["format"] == "league" else
                   {"top": 8, "ko": 24} if cfg["format"] == "league_phase_ko" else None),
        "slots": {"direct": cfg["_slots"][0], "next": cfg["_slots"][1], "next_label": cfg["_slots"][2]} if qualifying else None,
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
    past = past_seasons(by_slug, seasons)
    wanted.update(tb.pre_day(sm) for _, _, sm in past)
    elo, samples, snaps = run_club_elo(finished, hfa, wanted)

    h2h = h2h_index(finished)
    comps, rows = [], []
    cut = (t - timedelta(days=365)).isoformat()
    predicted = {c["slug"] for c in config.SOCCER_COMPETITIONS}
    for m in finished:
        if m["slug"] in predicted and m["date"] >= cut and m["id"] in elo.pre:
            rh, ra = elo.pre[m["id"]]
            p = gm.outcome_probs(rh + (0 if m["neutral"] else hfa) - ra)[:3]
            rows.append((p[0], p[1], p[2], outcome(m)))
    for cfg in config.SOCCER_COMPETITIONS:
        if any(slug == cfg["slug"] and y >= t.year - 1 for slug, y in FAILED):
            old = live_log.stale_copy("soccer", cfg["slug"], "ESPN didn't answer for this competition's latest results")
            if old:  # keep the last good predictions for this one; everything else still updates
                print("  ! %s: fetch failed, keeping the last good copy" % cfg["name"])
                comps.append(old)
                continue
        print("  simulating %s" % cfg["name"])
        payload = comp_payload(cfg, cfg["group"], seasons[cfg["slug"]], elo, gm, snaps, names, today_iso, h2h=h2h)
        comps.append(payload)
    print("  grading past title odds")
    graded = grade_past_seasons(past, snaps, gm, hfa, names)
    model = {"hfa": hfa, "goals_base": round(float(np.exp(gm.base)), 3), "slope": round(gm.slope, 3),
             "backtest": score_predictions(rows), "matches_rated": len(finished),
             "calibration": calibration([(r[i], int(r[3] == i)) for r in rows for i in range(3)]),
             "title_backtest": {"summary": tb.summarise(graded), "events": graded},
             "_histories": rating_histories(finished, elo, names, today_iso, days=400),
             "_ratings": {names.get(k, k): round(v) for k, v in elo.ratings.items() if k in names}}
    return comps, model


def past_seasons(by_slug, current, warmup_until="2022-07-01"):
    """Finished seasons we can grade: after the ratings' warm-up season, before the current one.

    Returns (cfg, season label, matches). UEFA competitions keep only their league phase, so the
    pre-season odds can't see any knockout draw.
    """
    out = []
    for cfg in config.SOCCER_COMPETITIONS:
        now = {m["season"] for m in current[cfg["slug"]]}
        by_season = {}
        for m in by_slug[cfg["slug"]]:
            by_season.setdefault(m["season"], []).append(m)
        for season, ms in sorted(by_season.items()):
            if season in now or any(m["status"] != "final" for m in ms):
                continue
            if cfg["format"] == "league_phase_ko":
                lp = [m["date"] for m in ms if "league" in m["stage"]]
                if not lp:
                    continue  # older format (group stage); not graded
                ms = [m for m in ms if m["date"] >= min(lp)]
            if min(m["date"] for m in ms) < warmup_until or len(ms) < 50:
                continue
            out.append((cfg, season_label(ms), ms))
    return out


def grade_past_seasons(past, snaps, gm, hfa, names, n=2000):
    rows = []
    for cfg, label, ms in past:
        d = tb.pre_day(ms)
        if d not in snaps:
            continue
        if cfg["format"] == "league":
            winner, sim_ms = tb.league_champion(ms), ms
        else:
            winner = tb.cup_champion(ms)
            sim_ms = [m for m in ms if "league" in m["stage"]]  # pre-season: only the league phase is fixed
        if not winner:
            continue
        odds = simulate_comp(cfg, as_of(sim_ms, d), snaps[d], gm, hfa, n, seed_for("bt", cfg["slug"], label))["p_win"]
        rows.append(tb.grade(cfg["name"], label, odds, winner, names))
    return rows


def intl_key(name):
    return config.COUNTRY_ALIASES.get(name, name)


def build_international(today_iso):
    t = date.fromisoformat(today_iso[:10])
    archive = load_international_results()
    last = max(r["date"] for r in archive)
    k_mult = lambda tour: next((k for s, k in INTL_K if s in tour), 1.5)
    rows = [{"id": "a%d" % i, "date": r["date"], "home": r["home"], "away": r["away"], "hg": r["hg"], "ag": r["ag"],
             "neutral": r["neutral"], "k_mult": k_mult(r["tournament"])} for i, r in enumerate(archive)
            if r["date"] <= today_iso[:10]]  # (only matters when replaying a past date)

    active = []
    for cfg in config.INTERNATIONAL_COMPETITIONS + config.WC_QUALIFYING:
        try:
            ms = load_slug(cfg["slug"], t.year - 2, t.year + 1)
        except RuntimeError:
            continue
        ms = as_of(ms, (t - timedelta(days=1)).isoformat()) if os.environ.get("SPORTSPRED_TODAY") else ms
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
    intl_h2h = h2h_index([dict(r, home_key=r["home"], away_key=r["away"]) for r in rows])

    comps = []
    for cfg, sm in active:
        if any(slug == cfg["slug"] and y >= t.year - 1 for slug, y in FAILED):
            old = live_log.stale_copy("soccer", cfg["slug"], "ESPN didn't answer for this competition's latest results")
            if old:
                print("  ! %s: fetch failed, keeping the last good copy" % cfg["name"])
                comps.append(old)
                continue
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
        if cfg["format"] == "qualifying":
            # this stage only: matches between two teams of the same group, slots from the stage's rules
            sm_kept = [m for m in sm if group_of.get(m["home_key"]) and group_of.get(m["home_key"]) == group_of.get(m["away_key"])]
            if not sm_kept:
                continue
            stage = max(sm_kept, key=lambda m: m["date"])["stage"]  # the latest round is the current one
            sm_kept = [m for m in sm_kept if m["stage"] == stage]
            cfg = dict(cfg, _slots=next(v for k, v in sorted(cfg["stages"].items(), key=lambda kv: -len(kv[0]))
                                        if k in stage))
        comps.append(comp_payload(cfg, cfg["group"], sm_kept, elo, gm, snaps, names, today_iso, groups, group_of,
                                  h2h=intl_h2h))

    cut = (t - timedelta(days=365)).isoformat()
    bt = []
    for r in rows:
        if r["date"] >= cut and r["id"] in elo.pre:
            rh, ra = elo.pre[r["id"]]
            p = gm.outcome_probs(rh + (0 if r["neutral"] else hfa) - ra)[:3]
            bt.append((p[0], p[1], p[2], outcome(r)))
    model = {"hfa": hfa, "goals_base": round(float(np.exp(gm.base)), 3), "slope": round(gm.slope, 3),
             "backtest": score_predictions(bt), "matches_rated": len(rows),
             "calibration": calibration([(r[i], int(r[3] == i)) for r in bt for i in range(3)])}
    teams_now = {r["team"] for c in comps for r in c.get("table", [])}
    model["_histories"] = rating_histories([dict(r, home_key=r["home"], away_key=r["away"]) for r in rows], elo,
                                           {t: t for t in teams_now}, today_iso, days=1500)
    model["_ratings"] = {t: round(elo.ratings[t]) for t in teams_now if t in elo.ratings}
    return comps, model


def write(comps):
    for c in comps:
        write_json(os.path.join(SITE_DATA_DIR, "soccer", c["id"] + ".json"), c)
