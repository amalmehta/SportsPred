"""Monte Carlo simulation of soccer competitions: league tables, UEFA's league phase, group stages and knockouts."""
import random
from collections import OrderedDict

import numpy as np

from .soccer_model import MAX_GOALS, poisson_pmf


class Matchups:
    """Expected goals for any pairing, given ratings + goals model. Caches knockout tie probabilities."""

    def __init__(self, ratings, goals_model, hfa, default_rating=1400.0):
        self.r, self.gm, self.hfa, self.default = ratings, goals_model, hfa, default_rating
        self._tie = {}

    def rating(self, t):
        return self.r.get(t, self.default)

    def lambdas(self, home, away, neutral=False):
        gap = self.rating(home) + (0 if neutral else self.hfa) - self.rating(away)
        return self.gm.lambdas(gap)

    def probs(self, home, away, neutral=False):
        gap = self.rating(home) + (0 if neutral else self.hfa) - self.rating(away)
        return self.gm.outcome_probs(gap)

    def _diff_pmf(self, home, away, neutral):
        lh, la = self.lambdas(home, away, neutral)
        return np.convolve(poisson_pmf(lh), poisson_pmf(la)[::-1])  # index k -> diff k-(MAX-1)

    def tie_prob(self, a, b, legs, agg=0):
        """P(a goes through). legs: remaining (home, away, neutral); agg: a's lead from legs already played.

        A level aggregate goes to extra time / penalties, split by each side's neutral-venue win share.
        """
        key = (a, b, tuple(legs), agg)
        if key in self._tie:
            return self._tie[key]
        dist = np.array([1.0])
        offset = 0  # dist[i] is P(diff = i - offset)
        for home, away, neutral in legs:
            d = self._diff_pmf(home, away, neutral)
            if home != a:
                d = d[::-1]
            dist = np.convolve(dist, d)
            offset += MAX_GOALS - 1
        diffs = np.arange(len(dist)) - offset + agg
        p_win, p_level = dist[diffs > 0].sum(), dist[diffs == 0].sum()
        ph, _, pa, _, _ = self.probs(a, b, neutral=True)
        share = ph / (ph + pa) if ph + pa > 0 else 0.5
        p = float((p_win + p_level * share) / dist.sum())
        self._tie[key] = p
        return p


# ---------------------------------------------------------------- tables

def table_from_results(teams, results):
    """Points / goal difference / goals for, from finished (home, away, hg, ag)."""
    tab = OrderedDict((t, [0, 0, 0, 0]) for t in teams)  # played, pts, gd, gf
    for h, a, hg, ag in results:
        for t, gf, ga in ((h, hg, ag), (a, ag, hg)):
            if t not in tab:
                continue
            row = tab[t]
            row[0] += 1
            row[1] += 3 if gf > ga else (1 if gf == ga else 0)
            row[2] += gf - ga
            row[3] += gf
    return tab


RATING_SD = 50.0  # how unsure we are of each team's true strength, in Elo points


def sim_table(teams, results, fixtures, mu, n, rng, rating_sd=RATING_SD):
    """Simulate remaining fixtures n times.

    Each simulation first nudges every team's rating by a random amount (sd = rating_sd), so a
    rating is treated as an estimate rather than the truth; without it long-range odds are overconfident.
    Returns (order, pts): order[s, k] = index of the team finishing k-th in sim s; pts[s, i] final points.
    """
    idx = {t: i for i, t in enumerate(teams)}
    base = table_from_results(teams, results)
    T = len(teams)
    pts = np.tile(np.array([base[t][1] for t in teams], dtype=float), (n, 1))
    gd = np.tile(np.array([base[t][2] for t in teams], dtype=float), (n, 1))
    gf = np.tile(np.array([base[t][3] for t in teams], dtype=float), (n, 1))
    noise = rng.normal(0.0, rating_sd, (n, T)) * (mu.gm.slope / 400.0)
    for h, a, neutral in fixtures:
        if h not in idx or a not in idx:
            continue
        i, j = idx[h], idx[a]
        lh, la = mu.lambdas(h, a, neutral)
        shift = np.exp(noise[:, i] - noise[:, j])
        gh, ga = rng.poisson(lh * shift, n), rng.poisson(la / shift, n)
        pts[:, i] += np.where(gh > ga, 3, np.where(gh == ga, 1, 0))
        pts[:, j] += np.where(ga > gh, 3, np.where(gh == ga, 1, 0))
        gd[:, i] += gh - ga
        gd[:, j] += ga - gh
        gf[:, i] += gh
        gf[:, j] += ga
    key = pts * 1e7 + (gd + 500) * 1e3 + gf + rng.random((n, T)) * 0.5
    order = np.argsort(-key, axis=1)
    return order, pts


# ---------------------------------------------------------------- knockouts

def _is_placeholder(m):
    bad = ("tbd", "winner", "loser", "runner")
    return any(w in (m["home"] or "").lower() or w in (m["away"] or "").lower() for w in bad)


def knockout_state(ko_matches):
    """Summarise knockout matches so far.

    Returns (stage_name, decided, open_ties): decided = teams through from the latest stage,
    open_ties = list of (a, b, remaining legs, a's aggregate lead). Returns None if no real ties.
    """
    stages = OrderedDict()
    for m in sorted(ko_matches, key=lambda m: m["date"]):
        if _is_placeholder(m):
            continue
        stages.setdefault(m["stage"], []).append(m)
    if not stages:
        return None
    stage, matches = list(stages.items())[-1]
    ties = OrderedDict()
    for m in matches:
        ties.setdefault(frozenset((m["home_key"], m["away_key"])), []).append(m)
    decided, open_ties = [], []
    for pair, legs in ties.items():
        a, b = legs[0]["home_key"], legs[0]["away_key"]
        agg, remaining = 0, []
        for m in legs:
            if m["status"] == "final":
                sign = 1 if m["home_key"] == a else -1
                agg += sign * (m["hg"] - m["ag"])
            else:
                remaining.append((m["home_key"], m["away_key"], m["neutral"]))
        if remaining:
            open_ties.append((a, b, tuple(remaining), agg))
        else:
            if agg > 0:
                decided.append(a)
            elif agg < 0:
                decided.append(b)
            else:  # level on aggregate: penalties, ESPN flags the winner on the last leg
                last = legs[-1]
                w = last.get("winner")
                if w == "home":
                    decided.append(last["home_key"])
                elif w == "away":
                    decided.append(last["away_key"])
                else:
                    decided.append(a)
    return stage, decided, open_ties


def run_bracket(alive, mu, two_leg_min, rng_py, fixed_pairs=False):
    """Play out a knockout from a list of surviving teams; returns the champion.

    Pairs neighbours in list order when fixed_pairs, otherwise draws pairings at random.
    Rounds with at least two_leg_min teams are two-legged; the final is one match on neutral ground.
    """
    alive = list(alive)
    while len(alive) > 1:
        if not fixed_pairs:
            rng_py.shuffle(alive)
        nxt = []
        if len(alive) % 2 == 1:  # odd field: one bye
            nxt.append(alive.pop())
        two_legs = len(alive) >= two_leg_min and len(alive) > 2
        for i in range(0, len(alive), 2):
            a, b = alive[i], alive[i + 1]
            legs = ((a, b, False), (b, a, False)) if two_legs else ((a, b, True),)
            nxt.append(a if rng_py.random() < mu.tie_prob(a, b, legs) else b)
        alive = nxt
    return alive[0]


def _resolve_open(decided, open_ties, mu, rng_py):
    through = list(decided)
    for a, b, legs, agg in open_ties:
        through.append(a if rng_py.random() < mu.tie_prob(a, b, legs, agg) else b)
    return through


def champion_counts(champs, teams):
    counts = {t: 0 for t in teams}
    for c in champs:
        counts[c] = counts.get(c, 0) + 1
    n = float(len(champs)) or 1.0
    return {t: counts[t] / n for t in counts}


# ---------------------------------------------------------------- formats

def place_odds(order, teams, top=None, bottom=None):
    """From simulated finishing orders: P(finish in the top `top`) and P(finish in the bottom `bottom`)."""
    pos = np.argsort(order, axis=1)  # pos[s, i] = finishing position of team i (0 = first)
    out = {}
    if top:
        out["p_top"] = {t: float((pos[:, i] < top).mean()) for i, t in enumerate(teams)}
    if bottom:
        out["p_drop"] = {t: float((pos[:, i] >= len(teams) - bottom).mean()) for i, t in enumerate(teams)}
    return out


def simulate_league(teams, results, fixtures, mu, n, seed, top=None, bottom=None):
    """Domestic league: champion = top of the table; also the chance of a top-`top` or bottom-`bottom` finish."""
    rng = np.random.default_rng(seed)
    order, pts = sim_table(teams, results, fixtures, mu, n, rng)
    p_win = np.bincount(order[:, 0], minlength=len(teams)) / float(n)
    out = {
        "p_win": {t: float(p_win[i]) for i, t in enumerate(teams)},
        "proj_pts": {t: float(pts[:, i].mean()) for i, t in enumerate(teams)},
    }
    out.update(place_odds(order, teams, top, bottom))
    return out


def ucl_bracket(ranked):
    """UEFA format after the 36-team league phase (ranked best first).

    9-24 play off (9 v 24, 10 v 23 ...); the playoff winners meet 1-8 (1 v winner of 16/17 ...);
    the round of 16 then runs as a fixed bracket. Returns the playoff ties and the order of R16 ties.
    """
    playoffs = [(ranked[r - 1], ranked[33 - r - 1]) for r in range(9, 17)]  # (9,24) ... (16,17)
    # seed s (1..8) meets the playoff tie that contains rank 17 - s
    r16_seeds = [1, 8, 4, 5, 2, 7, 3, 6]  # bracket order so 1 and 2 can only meet in the final
    return playoffs, r16_seeds


def simulate_league_phase_ko(lp_teams, lp_results, lp_fixtures, ko_matches, mu, n, seed):
    rng = np.random.default_rng(seed)
    rng_py = random.Random(seed)
    order, pts = sim_table(lp_teams, lp_results, lp_fixtures, mu, n, rng)
    state = knockout_state(ko_matches) if ko_matches else None
    champs = []
    if state is None:
        for s in range(n):
            ranked = [lp_teams[i] for i in order[s]]
            if len(ranked) < 24:
                champs.append(run_bracket(ranked[:8], mu, 4, rng_py))
                continue
            playoffs, seeds = ucl_bracket(ranked)
            po_winner = {}
            for a, b in playoffs:
                legs = ((b, a, False), (a, b, False))  # higher seed at home second
                po_winner[ranked.index(a) + 1] = a if rng_py.random() < mu.tie_prob(a, b, legs) else b
            r16 = []
            for sd in seeds:
                opp = po_winner[17 - sd]
                r16.extend([ranked[sd - 1], opp])
            champs.append(_bracket_fixed(r16, mu, rng_py))
    else:
        stage, decided, open_ties = state
        byes = []
        if "playoff" in stage:  # the top 8 skipped the playoff round
            byes = [lp_teams[i] for i in order[0][:8]]
        for s in range(n):
            alive = byes + _resolve_open(decided, open_ties, mu, rng_py)
            champs.append(run_bracket(alive, mu, 4, rng_py))
    out = place_odds(order, lp_teams, top=8)  # top 8 go straight to the round of 16
    out["p_ko"] = place_odds(order, lp_teams, top=24)["p_top"]  # top 24 reach the knockouts
    return dict(out, **{
        "p_win": champion_counts(champs, lp_teams),
        "proj_pts": {t: float(pts[:, i].mean()) for i, t in enumerate(lp_teams)},
    })


def _bracket_fixed(field, mu, rng_py):
    """Field is in bracket order: pairs (0,1), (2,3)... and winners keep their slots."""
    alive = list(field)
    while len(alive) > 1:
        nxt = []
        two_legs = len(alive) > 2
        for i in range(0, len(alive), 2):
            a, b = alive[i], alive[i + 1]
            legs = ((a, b, False), (b, a, False)) if two_legs else ((a, b, True),)
            nxt.append(a if rng_py.random() < mu.tie_prob(a, b, legs) else b)
        alive = nxt
    return alive[0]


def simulate_groups_ko(groups, results, fixtures, ko_matches, mu, n, seed, advance_top=2, two_leg_min=999):
    """Group tables, then a knockout. groups: {name: [teams]}."""
    rng = np.random.default_rng(seed)
    rng_py = random.Random(seed)
    all_teams = [t for g in groups.values() for t in g]
    state = knockout_state(ko_matches) if ko_matches else None
    champs = []
    proj = {}
    if state is not None:
        stage, decided, open_ties = state
        for s in range(n):
            champs.append(run_bracket(_resolve_open(decided, open_ties, mu, rng_py), mu, two_leg_min, rng_py))
        return {"p_win": champion_counts(champs, all_teams), "proj_pts": proj}
    per_group = {}
    for name, teams in groups.items():
        g_results = [r for r in results if r[0] in teams and r[1] in teams]
        g_fix = [f for f in fixtures if f[0] in teams and f[1] in teams]
        order, pts = sim_table(teams, g_results, g_fix, mu, n, rng)
        per_group[name] = (teams, order, pts)
        for i, t in enumerate(teams):
            proj[t] = float(pts[:, i].mean())
    names = list(groups)
    for s in range(n):
        winners, runners, thirds = [], [], []
        for name in names:
            teams, order, pts = per_group[name]
            ranked = [teams[i] for i in order[s]]
            winners.append(ranked[0])
            if advance_top >= 2 and len(ranked) > 1:
                runners.append(ranked[1])
            if len(ranked) > 2:
                thirds.append((pts[s, order[s][2]], ranked[2]))
        field = winners + runners
        size = 1
        while size < len(field):
            size *= 2
        if size > len(field):  # fill with the best third-placed teams
            thirds.sort(key=lambda x: -x[0])
            field += [t for _, t in thirds[: size - len(field)]]
        # group winners meet runners-up from a different group
        pairs = []
        k = len(runners)
        for i, w in enumerate(winners):
            if k:
                pairs.extend([w, runners[(i + 1) % k]])
        rest = [t for t in field if t not in pairs]
        bracket = pairs + rest
        if len(bracket) & (len(bracket) - 1):
            champs.append(run_bracket(bracket, mu, two_leg_min, rng_py))
        else:
            champs.append(run_bracket(bracket, mu, two_leg_min, rng_py, fixed_pairs=True))
    return {"p_win": champion_counts(champs, all_teams), "proj_pts": proj}


def simulate_qualifying(groups, results, fixtures, mu, n, seed, direct=1, nxt=1):
    """Qualifying groups: each table is simulated; finishing positions become places.

    Returns p_win (top the group), p_qualify (top `direct`), p_playoff (the `nxt` places after that).
    """
    rng = np.random.default_rng(seed)
    out = {"p_win": {}, "p_qualify": {}, "p_playoff": {}, "proj_pts": {}}
    for name, teams in groups.items():
        g_results = [r for r in results if r[0] in teams and r[1] in teams]
        g_fix = [f for f in fixtures if f[0] in teams and f[1] in teams]
        order, pts = sim_table(teams, g_results, g_fix, mu, n, rng)
        pos = np.argsort(order, axis=1)  # pos[s, i] = finishing position of team i in sim s (0 = top)
        for i, t in enumerate(teams):
            out["p_win"][t] = float((pos[:, i] == 0).mean())
            out["p_qualify"][t] = float((pos[:, i] < direct).mean())
            out["p_playoff"][t] = float(((pos[:, i] >= direct) & (pos[:, i] < direct + nxt)).mean())
            out["proj_pts"][t] = float(pts[:, i].mean())
    return out
