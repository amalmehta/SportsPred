"""Tennis player ratings (Elo) and tournament draw simulation."""
import math
import random
import re
from collections import defaultdict

from .common import day


def k_factor(n_matches):
    """FiveThirtyEight-style: new players' ratings move fast, veterans' slowly."""
    return 250.0 / ((n_matches + 5) ** 0.4)


def win_prob(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def best_of_five(p3):
    """Turn a best-of-3 match win chance into best-of-5 via the implied per-set chance."""
    lo, hi = 0.0, 1.0
    for _ in range(50):  # solve p3 = s^2 (3 - 2s) for the set-win chance s
        s = (lo + hi) / 2
        if s * s * (3 - 2 * s) < p3:
            lo = s
        else:
            hi = s
    s, q = (lo + hi) / 2, 1 - (lo + hi) / 2
    return s ** 3 * (1 + 3 * q + 6 * q * q)


class TennisElo:
    def __init__(self, init=1500.0):
        self.init = init
        self.ratings = {}
        self.n = defaultdict(int)
        self.names = {}
        self.pre = {}  # match id -> (rating a, rating b) before the match

    def rating(self, p):
        return self.ratings.get(p, self.init)

    def update(self, m):
        a, b = m["a"], m["b"]
        ra, rb = self.rating(a), self.rating(b)
        self.pre[m["id"]] = (ra, rb)
        e = win_prob(ra, rb)
        s = 1.0 if m["w"] == 0 else 0.0
        mult = m.get("k_mult", 1.0)
        self.ratings[a] = ra + mult * k_factor(self.n[a]) * (s - e)
        self.ratings[b] = rb - mult * k_factor(self.n[b]) * (s - e)
        self.n[a] += 1
        self.n[b] += 1
        self.names[a], self.names[b] = m["an"], m["bn"]

    def run(self, matches, snapshot_days=()):
        wanted = sorted(set(snapshot_days))
        snaps, wi = {}, 0
        for m in matches:
            d = day(m["date"])
            while wi < len(wanted) and wanted[wi] < d:
                snaps[wanted[wi]] = dict(self.ratings)
                wi += 1
            self.update(m)
        while wi < len(wanted):
            snaps[wanted[wi]] = dict(self.ratings)
            wi += 1
        return snaps


def rated_matches(events, grand_slam_names):
    """Flatten events into completed, decisive singles matches in date order."""
    out = []
    for ev in events:
        slam = any(s in ev["name"] for s in grand_slam_names)
        for m in ev["matches"]:
            if m["status"] != "final" or m["w"] is None or not m["a"] or not m["b"]:
                continue
            out.append(dict(m, k_mult=1.1 if slam else 1.0, event=ev["id"]))
    out.sort(key=lambda m: (m["date"] or "", round_rank(m["round"])))
    return out


def round_rank(name):
    n = (name or "").lower()
    if n.startswith("qual"):
        return 0 + (5 if "final" in n else 0)
    m = re.match(r"round (\d+)$", n)
    if m:
        return 10 + int(m.group(1))
    m = re.match(r"round of (\d+)", n)
    if m:
        return 20 - int(math.log2(int(m.group(1))))
    if "quarter" in n:
        return 90
    if "semi" in n:
        return 95
    if n == "final" or n.endswith(" final"):
        return 99
    return 50


def main_draw(event):
    """Main-draw rounds in order: [(round name, [matches])]."""
    rounds = defaultdict(list)
    for m in event["matches"]:
        if (m["round"] or "").lower().startswith("qual"):
            continue
        rounds[m["round"]].append(m)
    return [(r, rounds[r]) for r in sorted(rounds, key=round_rank)]


def as_of(event, d):
    """The draw as it stood at the end of day d: later results undone, later slots back to TBD."""
    rounds = main_draw(event)
    played = {}
    out = []
    for name, ms in rounds:
        new = []
        for m in ms:
            m = dict(m)
            for slot in ("a", "b"):
                p = m[slot]
                if p and p in played and not played[p]:
                    m[slot], m[slot + "n"] = None, "TBD"
            done = m["status"] in ("final", "retired", "walkover") and day(m["date"]) <= d
            if not done:
                m["status"], m["w"] = "scheduled", None
            for slot, idx in (("a", 0), ("b", 1)):
                if m[slot]:
                    played[m[slot]] = done and m["w"] == idx  # still in only if they won by day d
            new.append(m)
        out.append((name, new))
    return out


def simulate_draw(rounds, ratings, best_of_5, n, seed, default_rating=None):
    """Monte Carlo over the remaining draw. Returns {player id: P(title)}.

    ESPN doesn't publish bracket positions, so known players are linked to the match they came
    from; open slots (TBD) take winners of unlinked matches from the round before, drawn at random.
    """
    rng = random.Random(seed)
    if not rounds:
        return {}
    known = [r for r in ratings.values()]
    default = default_rating or (sorted(known)[len(known) // 5] if known else 1500.0)
    rate = lambda p: ratings.get(p, default)
    prob_cache = {}

    def p_win(a, b):
        key = (a, b)
        if key not in prob_cache:
            p = win_prob(rate(a), rate(b))
            prob_cache[key] = best_of_five(p) if best_of_5 else p
        return prob_cache[key]

    # link each known player to the match they played in the previous round
    feeds = []
    for r in range(1, len(rounds)):
        prev = rounds[r - 1][1]
        where = {}
        for m in prev:
            for slot in ("a", "b"):
                if m[slot]:
                    where[m[slot]] = m["id"]
        linked = set()
        for m in rounds[r][1]:
            for slot in ("a", "b"):
                if m[slot] in where:
                    linked.add(where[m[slot]])
        feeds.append([m["id"] for m in prev if m["id"] not in linked])

    wins = defaultdict(int)
    for s in range(n):
        winner = {}
        orphans = []
        for r, (name, ms) in enumerate(rounds):
            if r > 0:
                orphans = [winner[i] for i in feeds[r - 1] if i in winner]
                rng.shuffle(orphans)
            for m in ms:
                a, b = m["a"], m["b"]
                if a is None:
                    a = orphans.pop() if orphans else ("Q", m["id"], 0)
                if b is None:
                    b = orphans.pop() if orphans else ("Q", m["id"], 1)
                if m["status"] in ("final", "retired", "walkover") and m["w"] is not None:
                    winner[m["id"]] = a if m["w"] == 0 else b
                else:
                    winner[m["id"]] = a if rng.random() < p_win(a, b) else b
        final = rounds[-1][1]
        champ = winner[final[0]["id"]] if final else None
        if champ is not None and not isinstance(champ, tuple):
            wins[champ] += 1
    return {p: c / float(n) for p, c in wins.items()}
