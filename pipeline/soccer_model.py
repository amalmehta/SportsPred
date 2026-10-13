"""Soccer ratings (Elo) and the goals model that turns two ratings into match probabilities.

Elo gives each team one number. Before a match, the rating gap (plus home advantage) sets how
many goals each side is expected to score; goals are treated as Poisson draws. That one
model produces win/draw/loss chances, likely scores, and drives the season simulations.
"""
import math
from collections import defaultdict

import numpy as np

from .common import day

MAX_GOALS = 11


def gd_multiplier(gd):
    """Bigger wins move ratings more (World Football Elo style)."""
    gd = abs(gd)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11.0 + gd) / 8.0


class GoalsModel:
    """log(goals) = base +/- slope * (rating gap / 400)."""

    def __init__(self, base=math.log(1.35), slope=0.85):
        self.base, self.slope = base, slope

    def lambdas(self, gap):
        """gap = home rating + home advantage - away rating (Elo points)."""
        x = self.slope * gap / 400.0
        return math.exp(self.base + x), math.exp(self.base - x)

    def outcome_probs(self, gap):
        lh, la = self.lambdas(gap)
        ph, pa = poisson_pmf(lh), poisson_pmf(la)
        grid = np.outer(ph, pa)
        home = float(np.tril(grid, -1).sum())
        draw = float(np.trace(grid))
        away = float(np.triu(grid, 1).sum())
        s = home + draw + away
        i, j = np.unravel_index(np.argmax(grid), grid.shape)
        return home / s, draw / s, away / s, (int(i), int(j)), (lh, la)


def poisson_pmf(lam, n=MAX_GOALS):
    k = np.arange(n)
    logp = k * math.log(max(lam, 1e-9)) - lam - np.array([math.lgamma(i + 1) for i in k])
    return np.exp(logp)


class Elo:
    """Sequential Elo over a list of matches sorted by date.

    match dict needs: date, home, away (team keys), hg, ag, neutral; optional k_mult, slug.
    """

    def __init__(self, k=20.0, hfa=60.0, init=1500.0, new_team_rating=None):
        self.k, self.hfa, self.init = k, hfa, init
        self.ratings = {}
        self.games = defaultdict(int)
        self.new_team_rating = new_team_rating  # callable(team, match, elo) -> rating
        self.pre = {}   # match id -> (home rating, away rating) before the match

    def rating(self, team, match=None):
        if team not in self.ratings:
            r = self.new_team_rating(team, match, self) if self.new_team_rating else self.init
            self.ratings[team] = r
        return self.ratings[team]

    def gap(self, home, away, neutral):
        return self.rating(home) + (0 if neutral else self.hfa) - self.rating(away)

    def update(self, m):
        rh, ra = self.rating(m["home"], m), self.rating(m["away"], m)
        if m.get("id") is not None:
            self.pre[m["id"]] = (rh, ra)
        g = rh + (0 if m.get("neutral") else self.hfa) - ra
        expected = 1.0 / (1.0 + 10 ** (-g / 400.0))
        actual = 1.0 if m["hg"] > m["ag"] else (0.5 if m["hg"] == m["ag"] else 0.0)
        # new teams settle faster
        k = self.k * m.get("k_mult", 1.0)
        kh = k * (1.5 if self.games[m["home"]] < 30 else 1.0)
        ka = k * (1.5 if self.games[m["away"]] < 30 else 1.0)
        mult = gd_multiplier(m["hg"] - m["ag"])
        self.ratings[m["home"]] = rh + kh * mult * (actual - expected)
        self.ratings[m["away"]] = ra - ka * mult * (actual - expected)
        self.games[m["home"]] += 1
        self.games[m["away"]] += 1
        return rh, ra

    def run(self, matches, snapshot_days=(), on_match=None):
        """Process finished matches in order. Returns {day: ratings copy taken after that day's matches}."""
        wanted = sorted(set(snapshot_days))
        snaps, wi = {}, 0
        for m in matches:
            d = day(m["date"])
            while wi < len(wanted) and wanted[wi] < d:
                snaps[wanted[wi]] = dict(self.ratings)
                wi += 1
            rh, ra = self.update(m)
            if on_match:
                on_match(m, rh, ra)
        while wi < len(wanted):
            snaps[wanted[wi]] = dict(self.ratings)
            wi += 1
        return snaps


def fit_goals_model(samples):
    """Fit base and slope by maximum likelihood. samples: list of (gap, hg, ag)."""
    if not samples:
        return GoalsModel()
    gaps = np.array([s[0] for s in samples]) / 400.0
    hg = np.array([s[1] for s in samples], dtype=float)
    ag = np.array([s[2] for s in samples], dtype=float)
    best = None
    for slope in np.arange(0.3, 1.81, 0.05):
        # for a fixed slope the best base has a closed form
        e = np.exp(slope * gaps)
        base = math.log((hg.sum() + ag.sum()) / (e.sum() + (1 / e).sum()))
        lh, la = np.exp(base + slope * gaps), np.exp(base - slope * gaps)
        ll = (hg * np.log(lh) - lh).sum() + (ag * np.log(la) - la).sum()
        if best is None or ll > best[0]:
            best = (ll, base, slope)
    return GoalsModel(best[1], best[2])


def score_predictions(rows):
    """rows: list of (p_home, p_draw, p_away, outcome 0/1/2). Returns accuracy/Brier/log-loss."""
    if not rows:
        return {"n": 0}
    acc = brier = ll = 0.0
    draw_pred = draw_act = 0.0
    for ph, pd, pa, o in rows:
        p = (ph, pd, pa)
        acc += 1 if max(range(3), key=lambda i: p[i]) == o else 0
        brier += sum((p[i] - (1 if i == o else 0)) ** 2 for i in range(3))
        ll += -math.log(max(p[o], 1e-9))
        draw_pred += pd
        draw_act += 1 if o == 1 else 0
    n = len(rows)
    return {"n": n, "accuracy": acc / n, "brier": brier / n, "log_loss": ll / n,
            "draw_rate_predicted": draw_pred / n, "draw_rate_actual": draw_act / n}
