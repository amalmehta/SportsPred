"""Did the favourites win? Grade pre-season / pre-tournament title odds against actual champions.

For every finished season or tournament we cover, the odds are rebuilt as they stood the day before it
started (ratings from that day, every match still to play) and compared with who actually won.
"""
import math
from datetime import date, timedelta

from .common import day


def pre_day(matches):
    """The day before the first match."""
    first = min(day(m["date"]) for m in matches if m.get("date"))
    return (date.fromisoformat(first) - timedelta(days=1)).isoformat()


def grade(name, season, odds, winner, names=None):
    """One event's row: how much chance the eventual winner was given, and where they ranked."""
    names = names or {}
    ranked = sorted(odds.items(), key=lambda kv: -kv[1])
    fav, p_fav = ranked[0] if ranked else (None, 0.0)
    p_win = odds.get(winner, 0.0)
    rank = next((i + 1 for i, (k, _) in enumerate(ranked) if k == winner), len(ranked) + 1)
    return {"name": name, "season": season, "winner": names.get(winner, winner), "p_winner": round(p_win, 4),
            "rank": rank, "favourite": names.get(fav, fav), "p_favourite": round(p_fav, 4), "field": len(odds)}


def summarise(rows):
    """Headline numbers over many events. Field-size baseline: every entrant equally likely."""
    if not rows:
        return {"n": 0}
    n = float(len(rows))
    eps = 1e-3  # a champion we gave ~0% would otherwise dominate the average log loss
    return {
        "n": len(rows),
        "favourite_won": sum(1 for r in rows if r["rank"] == 1),
        "winner_in_top3": sum(1 for r in rows if r["rank"] <= 3),
        "avg_p_winner": round(sum(r["p_winner"] for r in rows) / n, 4),
        "avg_p_baseline": round(sum(1.0 / max(r["field"], 1) for r in rows) / n, 4),
        "log_loss": round(sum(-math.log(max(r["p_winner"], eps)) for r in rows) / n, 4),
    }


def league_champion(matches):
    """Top of the final table: points, then goal difference, then goals scored."""
    tab = {}
    for m in matches:
        if m["status"] != "final":
            continue
        for t, gf, ga in ((m["home_key"], m["hg"], m["ag"]), (m["away_key"], m["ag"], m["hg"])):
            r = tab.setdefault(t, [0, 0, 0])
            r[0] += 3 if gf > ga else (1 if gf == ga else 0)
            r[1] += gf - ga
            r[2] += gf
    return max(tab, key=lambda t: tab[t]) if tab else None


def cup_champion(matches):
    """Winner of the last match in the competition's final."""
    finals = [m for m in matches if m["status"] == "final" and m.get("stage", "").strip("-") in ("final", "finals")]
    if not finals:
        return None
    m = max(finals, key=lambda m: m["date"])
    if m.get("winner") == "home" or (m.get("winner") != "away" and m["hg"] > m["ag"]):
        return m["home_key"]
    return m["away_key"]
