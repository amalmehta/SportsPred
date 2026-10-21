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


def low_score_factors(lh, la, rho):
    """Dixon-Coles: independent Poisson goals slightly miss how often games end 0-0, 1-0, 0-1 and 1-1.
    These factors scale those four scores (rho < 0 means more 0-0 and 1-1, fewer 1-0 and 0-1)."""
    return {(0, 0): 1 - lh * la * rho, (0, 1): 1 + lh * rho, (1, 0): 1 + la * rho, (1, 1): 1 - rho + 0 * lh}


def score_grid(lh, la, rho=0.0, n=MAX_GOALS):
    """P(home scores i, away scores j), with the low-score correction; sums to 1."""
    g = np.outer(poisson_pmf(lh, n), poisson_pmf(la, n))
    if rho:
        for (i, j), f in low_score_factors(lh, la, rho).items():
            g[i, j] *= f
    return g / g.sum()


class GoalsModel:
    """log(goals) = base +/- slope * (rating gap / 400); goals Poisson with a low-score correction (rho)."""

    def __init__(self, base=math.log(1.35), slope=0.85, rho=0.0):
        self.base, self.slope, self.rho = base, slope, rho

    def lambdas(self, gap):
        """gap = home rating + home advantage - away rating (Elo points)."""
        x = self.slope * gap / 400.0
        return math.exp(self.base + x), math.exp(self.base - x)

    def outcome_probs(self, gap):
        lh, la = self.lambdas(gap)
        grid = score_grid(lh, la, self.rho)
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
        g = rh + (0 if m.get("neutral") else self.hfa + m.get("hfa_add", 0.0)) - ra
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


def no_skill(rows):
    """What you'd score knowing only how often home wins, draws and away wins happen in these matches:
    always pick the commonest result, and give every match those same three chances."""
    if not rows:
        return {"n": 0}
    n = float(len(rows))
    freq = [sum(1 for r in rows if r[3] == o) / n for o in range(3)]
    return {"n": len(rows), "accuracy": max(freq), "log_loss": -sum(f * math.log(f) for f in freq if f > 0)}


def by_competition(rows, names):
    """rows: (competition id, p_home, p_draw, p_away, outcome). One accuracy line per competition, with
    the no-skill baseline beside it; skill = how much lower our log loss is than the baseline's."""
    out = []
    for cid in names:
        mine = [r[1:] for r in rows if r[0] == cid]
        if len(mine) < 20:
            continue
        ours, base = score_predictions(mine), no_skill(mine)
        out.append({"id": cid, "name": names[cid], "n": ours["n"], "accuracy": round(ours["accuracy"], 4),
                    "log_loss": round(ours["log_loss"], 4), "base_accuracy": round(base["accuracy"], 4),
                    "base_log_loss": round(base["log_loss"], 4),
                    "skill": round(1 - ours["log_loss"] / base["log_loss"], 4)})
    return out


def fit_low_score(gm, samples, grid=np.arange(-0.20, 0.0501, 0.01)):
    """Pick the Dixon-Coles rho that best explains the exact scores, for a goals model already fitted.
    samples: (gap, hg, ag). Only the four low scores and the normaliser change with rho, so this is quick."""
    if not samples:
        return 0.0
    gaps = np.array([s[0] for s in samples]) / 400.0
    hg = np.array([s[1] for s in samples])
    ag = np.array([s[2] for s in samples])
    lh, la = np.exp(gm.base + gm.slope * gaps), np.exp(gm.base - gm.slope * gaps)
    p0h, p0a = np.exp(-lh), np.exp(-la)
    cells = {(0, 0): p0h * p0a, (0, 1): p0h * p0a * la, (1, 0): p0h * lh * p0a, (1, 1): p0h * lh * p0a * la}
    best = (None, 0.0)
    for rho in grid:
        f = low_score_factors(lh, la, rho)
        if any((v <= 0).any() for v in f.values()):
            continue
        z = 1 + sum(cells[k] * (f[k] - 1) for k in cells)
        ll = -np.log(z).sum()
        for (i, j), v in f.items():
            hit = (hg == i) & (ag == j)
            ll += np.log(v[hit]).sum()
        if best[0] is None or ll > best[0]:
            best = (ll, float(rho))
    return round(best[1], 3)
