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


def sim_table(teams, results, fixtures, mu, n, rng, rating_sd=RATING_SD, track=0):
    """Simulate remaining fixtures n times.

    Each simulation first nudges every team's rating by a random amount (sd = rating_sd), so a
    rating is treated as an estimate rather than the truth; without it long-range odds are overconfident.
    Returns (order, pts): order[s, k] = index of the team finishing k-th in sim s; pts[s, i] final points.
    With track=k, also returns the simulated outcome (0 home win, 1 draw, 2 away win) of the first k
    fixtures: a list of (fixture position, outcomes array), used to measure how much each game matters.
    """
    idx = {t: i for i, t in enumerate(teams)}
    base = table_from_results(teams, results)
    T = len(teams)
    pts = np.tile(np.array([base[t][1] for t in teams], dtype=float), (n, 1))
    gd = np.tile(np.array([base[t][2] for t in teams], dtype=float), (n, 1))
    gf = np.tile(np.array([base[t][3] for t in teams], dtype=float), (n, 1))
    noise = rng.normal(0.0, rating_sd, (n, T)) * (mu.gm.slope / 400.0)
    tracked = []
    for k, (h, a, neutral) in enumerate(fixtures):
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
        if len(tracked) < track:
            tracked.append((k, np.where(gh > ga, 0, np.where(gh == ga, 1, 2))))
    key = pts * 1e7 + (gd + 500) * 1e3 + gf + rng.random((n, T)) * 0.5
    order = np.argsort(-key, axis=1)
    if track:
        return order, pts, tracked
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


def match_swings(tracked, champion, fixtures, teams, p_win, min_share=0.02, keep=5):
    """How much each upcoming game moves the title race.

    Within the simulations, the title chance of each contender is split by that game's result
    (home win / draw / away win). The swing is the biggest gap between results for any contender.
    """
    n = float(len(champion))
    contenders = [i for i in np.argsort(-p_win)[:3] if p_win[i] >= 0.05]
    out = []
    for k, outcome in tracked:
        share = [float((outcome == o).mean()) for o in range(3)]
        cond, swing = {}, 0.0
        for i in contenders:
            vals = [float((champion[outcome == o] == i).mean()) if share[o] >= min_share else None for o in range(3)]
            seen = [v for v in vals if v is not None]
            swing = max(swing, (max(seen) - min(seen)) if len(seen) > 1 else 0.0)
            cond[teams[i]] = [round(v, 3) if v is not None else None for v in vals]
        h, a, _ = fixtures[k]
        out.append({"home_key": h, "away_key": a, "swing": round(swing, 3), "share": [round(x, 3) for x in share],
                    "if": cond})
    out.sort(key=lambda x: -x["swing"])
    return [x for x in out if x["swing"] >= 0.02][:keep]


def simulate_league(teams, results, fixtures, mu, n, seed, top=None, bottom=None, track=0):
    """Domestic league: champion = top of the table; also the chance of a top-`top` or bottom-`bottom` finish.
    With track=k, also says which of the next k games swing the title race most (see match_swings)."""
    rng = np.random.default_rng(seed)
    res = sim_table(teams, results, fixtures, mu, n, rng, track=track)
    order, pts = res[0], res[1]
    p_win = np.bincount(order[:, 0], minlength=len(teams)) / float(n)
    out = {
        "p_win": {t: float(p_win[i]) for i, t in enumerate(teams)},
        "proj_pts": {t: float(pts[:, i].mean()) for i, t in enumerate(teams)},
    }
    out.update(place_odds(order, teams, top, bottom))
    pos = np.argsort(order, axis=1)  # pos[s, i] = where team i finished in sim s (0 = top)
    out["positions"] = {t: np.bincount(pos[:, i], minlength=len(teams)) / float(n) for i, t in enumerate(teams)}
    if track:
        out["swings"] = match_swings(res[2], order[:, 0], fixtures, teams, p_win)
    return out


# ---------------------------------------------------------------- UEFA league-phase knockouts

def ko_round(stage):
    """ESPN stage slug -> knockout round: po, r16, qf, sf, f (None if not a knockout round)."""
    st = stage or ""
    if "playoff" in st:
        return "po"
    if "16" in st:
        return "r16"
    if "quarter" in st:
        return "qf"
    if "semi" in st:
        return "sf"
    if st.strip("-") in ("final", "finals"):
        return "f"
    return None


def real_ties(ko_matches):
    """{round: {frozenset(a, b): (a, remaining legs, a's aggregate lead, winner or None)}} from ESPN."""
    by_round = {}
    for m in sorted(ko_matches, key=lambda m: m["date"]):
        rnd = ko_round(m["stage"])
        if rnd and not _is_placeholder(m):
            by_round.setdefault(rnd, {}).setdefault(frozenset((m["home_key"], m["away_key"])), []).append(m)
    out = {}
    for rnd, ties in by_round.items():
        for pair, legs in ties.items():
            a = legs[0]["home_key"]
            agg, remaining = 0, []
            for m in legs:
                if m["status"] == "final":
                    agg += (1 if m["home_key"] == a else -1) * (m["hg"] - m["ag"])
                else:
                    remaining.append((m["home_key"], m["away_key"], m["neutral"]))
            winner = None
            if not remaining:
                if agg:
                    winner = a if agg > 0 else next(iter(pair - {a}))
                else:  # level: decided on penalties, which ESPN flags on the last leg
                    last = legs[-1]
                    winner = last["home_key"] if last.get("winner") == "home" else last["away_key"]
            out.setdefault(rnd, {})[pair] = (a, tuple(remaining), agg, winner)
    return out


# league-phase positions that meet in the playoffs (seeded pair v unseeded pair), and which seeds
# (1..8) the winners of each pool face in the round of 16
PLAYOFF_POOLS = [((15, 16), (17, 18), (1, 2)), ((13, 14), (19, 20), (3, 4)),
                 ((11, 12), (21, 22), (5, 6)), ((9, 10), (23, 24), (7, 8))]
R16_ORDER = [1, 8, 4, 5, 2, 7, 3, 6]  # bracket order of the seeds' ties: 1 and 2 only meet in the final


def uefa_knockout(ranked, ties, mu, rng_py):
    """One run of the UEFA knockout from a final league-phase order (best first). Returns the champion.

    Follows the 2024- format: 9-24 play off in seeded pools, the winners meet 1-8, and the bracket is
    fixed from the round of 16. Real ties (pairings and results) from ESPN override the simulated draw.
    """
    pos = {t: i + 1 for i, t in enumerate(ranked)}

    def play(rnd, a, b):
        real = ties.get(rnd, {}).get(frozenset((a, b)))
        if real:
            a0, remaining, agg, winner = real
            if winner:
                return winner
            p = mu.tie_prob(a0, next(iter({a, b} - {a0})), remaining, agg)
            return a0 if rng_py.random() < p else next(iter({a, b} - {a0}))
        if rnd == "f":
            legs = ((a, b, True),)
        else:  # better-placed side at home in the second leg
            hi, lo = (a, b) if pos.get(a, 99) < pos.get(b, 99) else (b, a)
            legs = ((lo, hi, False), (hi, lo, False))
        return a if rng_py.random() < mu.tie_prob(a, b, legs) else b

    def real_partner(rnd, team):
        for pair in ties.get(rnd, {}):
            if team in pair:
                return next(iter(pair - {team}))
        return None

    # playoffs, pool by pool; then each pool's two winners meet that pool's two seeds
    seed_opponent = {}
    for seeded, unseeded, seeds in PLAYOFF_POOLS:
        tops = [ranked[i - 1] for i in seeded]
        bottoms = [ranked[i - 1] for i in unseeded]
        rng_py.shuffle(bottoms)
        pairs = []
        for t in tops:
            partner = real_partner("po", t)
            if partner in bottoms:
                bottoms.remove(partner)
            else:
                partner = bottoms.pop()
            pairs.append((t, partner))
        winners = [play("po", a, b) for a, b in pairs]
        seed_teams = [ranked[i - 1] for i in seeds]
        rng_py.shuffle(winners)
        for st in seed_teams:
            partner = real_partner("r16", st)
            w = partner if partner in winners else winners[-1]
            winners.remove(w)
            seed_opponent[st] = w
    field = []
    for sd in R16_ORDER:
        st = ranked[sd - 1]
        field.extend([st, seed_opponent[st]])
    # fixed bracket from here; a real pairing for a later round wins if ESPN has one
    for rnd in ("r16", "qf", "sf", "f"):
        nxt = []
        for i in range(0, len(field), 2):
            a, b = field[i], field[i + 1]
            real_b = real_partner(rnd, a)
            if real_b and real_b != b and real_b in field[i + 2:]:
                j = field.index(real_b, i + 2)  # ESPN's draw differs from our bracket: follow ESPN
                field[j], field[i + 1] = field[i + 1], field[j]
                b = real_b
            nxt.append(play(rnd, a, b))
        field = nxt
    return field[0]


def simulate_league_phase_ko(lp_teams, lp_results, lp_fixtures, ko_matches, mu, n, seed):
    rng = np.random.default_rng(seed)
    rng_py = random.Random(seed)
    order, pts = sim_table(lp_teams, lp_results, lp_fixtures, mu, n, rng)
    ties = real_ties(ko_matches or [])
    champs = []
    for s in range(n):
        ranked = [lp_teams[i] for i in order[s]]
        if len(ranked) < 24:  # not the 36-team format: plain bracket of the top 8
            champs.append(run_bracket(ranked[:8], mu, 4, rng_py))
        else:
            champs.append(uefa_knockout(ranked, ties, mu, rng_py))
    out = place_odds(order, lp_teams, top=8)  # top 8 go straight to the round of 16
    out["p_ko"] = place_odds(order, lp_teams, top=24)["p_top"]  # top 24 reach the knockouts
    return dict(out, **{
        "p_win": champion_counts(champs, lp_teams),
        "proj_pts": {t: float(pts[:, i].mean()) for i, t in enumerate(lp_teams)},
    })


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
