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


def set_prob(p3):
    """The chance of winning a set implied by a best-of-3 match chance: solve p3 = s^2 (3 - 2s)."""
    lo, hi = 0.0, 1.0
    for _ in range(50):
        s = (lo + hi) / 2
        if s * s * (3 - 2 * s) < p3:
            lo = s
        else:
            hi = s
    return (lo + hi) / 2


def best_of_five(p3):
    """Turn a best-of-3 match win chance into best-of-5 via the implied per-set chance."""
    s = set_prob(p3)
    q = 1 - s
    return s ** 3 * (1 + 3 * q + 6 * q * q)


def sets_won(sc):
    """Sets won by each player from a score like [[6, 3], [6, 7], [7, 5]] -> (2, 1)."""
    a = sum(1 for x, y in sc or [] if x > y)
    b = sum(1 for x, y in sc or [] if y > x)
    return a, b


SURFACES = ("hard", "clay", "grass")


def surface_of(name, table):
    """'clay' / 'grass' from the tournament-name lookup in config; everything else is 'hard'."""
    low = (name or "").lower()
    for surface, keys in table.items():
        if any(k.lower() in low for k in keys):
            return surface
    return "hard"


class TennisElo:
    """Two ratings per player: overall (every match) and one per surface (matches on that surface only).

    A prediction blends them: (1 - weight) * overall + weight * surface. The weight is fitted on results.
    """

    def __init__(self, init=1500.0, weight=0.5):
        self.init, self.weight = init, weight
        self.ratings = {}
        self.surf = {s: {} for s in SURFACES}
        self.n = defaultdict(int)
        self.ns = {s: defaultdict(int) for s in SURFACES}
        self.names = {}
        self.pre = {}  # match id -> (overall a, overall b, surface a, surface b) before the match

    def rating(self, p, surface=None):
        overall = self.ratings.get(p, self.init)
        if surface is None:
            return overall
        return (1 - self.weight) * overall + self.weight * self.surf[surface].get(p, self.init)

    def ratings_for(self, surface):
        """Blended rating of every known player on one surface."""
        return {p: self.rating(p, surface) for p in self.ratings}

    def pre_rating(self, match_id, weight=None):
        w = self.weight if weight is None else weight
        oa, ob, sa, sb = self.pre[match_id]
        return (1 - w) * oa + w * sa, (1 - w) * ob + w * sb

    def update(self, m):
        a, b = m["a"], m["b"]
        surface = m.get("surface", "hard")
        sr = self.surf[surface]
        ra, rb = self.ratings.get(a, self.init), self.ratings.get(b, self.init)
        sa, sb = sr.get(a, self.init), sr.get(b, self.init)
        self.pre[m["id"]] = (ra, rb, sa, sb)
        s = 1.0 if m["w"] == 0 else 0.0
        mult = m.get("k_mult", 1.0)
        e = win_prob(ra, rb)
        self.ratings[a] = ra + mult * k_factor(self.n[a]) * (s - e)
        self.ratings[b] = rb - mult * k_factor(self.n[b]) * (s - e)
        e = win_prob(sa, sb)
        ns = self.ns[surface]
        sr[a] = sa + mult * k_factor(ns[a]) * (s - e)
        sr[b] = sb - mult * k_factor(ns[b]) * (s - e)
        self.n[a] += 1
        self.n[b] += 1
        ns[a] += 1
        ns[b] += 1
        self.names[a], self.names[b] = m["an"], m["bn"]

    def snapshot(self):
        return dict(self.ratings), {s: dict(r) for s, r in self.surf.items()}

    def blend_snapshot(self, snap, surface):
        overall, surf = snap
        w, sr = self.weight, surf[surface]
        return {p: (1 - w) * r + w * sr.get(p, self.init) for p, r in overall.items()}

    def run(self, matches, snapshot_days=()):
        """Process matches in order. Returns {day: snapshot taken after that day's matches}."""
        wanted = sorted(set(snapshot_days))
        snaps, wi = {}, 0
        for m in matches:
            d = day(m["date"])
            while wi < len(wanted) and wanted[wi] < d:
                snaps[wanted[wi]] = self.snapshot()
                wi += 1
            self.update(m)
        while wi < len(wanted):
            snaps[wanted[wi]] = self.snapshot()
            wi += 1
        return snaps


def score(elo, matches, weight):
    """Accuracy / Brier / log loss of pre-match predictions at a given surface weight."""
    n = acc = brier = ll = 0.0
    for m in matches:
        ra, rb = elo.pre_rating(m["id"], weight)
        p = win_prob(ra, rb)
        y = 1 if m["w"] == 0 else 0
        n += 1
        acc += 1 if (p >= 0.5) == (y == 1) else 0
        brier += (p - y) ** 2
        ll += -math.log(max(p if y else 1 - p, 1e-9))
    if not n:
        return {"n": 0}
    return {"n": int(n), "accuracy": acc / n, "brier": brier / n, "log_loss": ll / n}


def fit_surface_weight(elo, matches, grid=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)):
    """Pick the overall/surface blend with the lowest log loss on these matches."""
    return min(grid, key=lambda w: score(elo, matches, w).get("log_loss", 9.9))


def rated_matches(events, grand_slam_names, surfaces=None):
    """Flatten events into completed, decisive singles matches in date order, tagged with surface."""
    out = []
    for ev in events:
        slam = any(s in ev["name"] for s in grand_slam_names)
        surface = surface_of(ev["name"], surfaces or {})
        for m in ev["matches"]:
            if m["status"] != "final" or m["w"] is None or not m["a"] or not m["b"]:
                continue
            out.append(dict(m, k_mult=1.1 if slam else 1.0, event=ev["id"], surface=surface))
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


REACH_ROUNDS = {"quarter": "qf", "semi": "sf", "final": "f"}  # round name contains -> short key


def reach_key(name):
    n = (name or "").lower()
    if n == "final" or n.endswith(" final") and not n.startswith("qual"):
        return "f"
    for k, v in REACH_ROUNDS.items():
        if n.startswith(k):
            return v
    return None


def simulate_draw(rounds, ratings, best_of_5, n, seed, default_rating=None, reach=None):
    """Monte Carlo over the remaining draw. Returns {player id: P(title)}.

    Pass a dict as `reach` to also get {"qf"|"sf"|"f": {player id: P(reach that round)}}, plus
    "finals": {(player, player): P(that pair contests the final)} and "next": {match id: {opponent: P}}
    for listed matches with one player known and the other still to be decided ("Q" = a qualifier).

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
    reached = {k: defaultdict(int) for k in ("qf", "sf", "f")}
    finals = defaultdict(int)
    nxt = defaultdict(lambda: defaultdict(int))
    half = {m["id"] for _, ms in rounds for m in ms
            if (m["a"] is None) != (m["b"] is None) and m["status"] not in ("final", "retired", "walkover")}
    keys = [reach_key(name) for name, _ in rounds]
    last = len(rounds) - 1
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
                if keys[r] and reach is not None:
                    for p in (a, b):
                        if not isinstance(p, tuple):
                            reached[keys[r]][p] += 1
                if r == last and len(ms) == 1 and not isinstance(a, tuple) and not isinstance(b, tuple):
                    finals[tuple(sorted((a, b)))] += 1
                if m["id"] in half and reach is not None:
                    opp = b if m["a"] is not None else a
                    nxt[m["id"]]["Q" if isinstance(opp, tuple) else opp] += 1
                if m["status"] in ("final", "retired", "walkover") and m["w"] is not None:
                    winner[m["id"]] = a if m["w"] == 0 else b
                else:
                    winner[m["id"]] = a if rng.random() < p_win(a, b) else b
        final = rounds[-1][1]
        champ = winner[final[0]["id"]] if final else None
        if champ is not None and not isinstance(champ, tuple):
            wins[champ] += 1
    if reach is not None:
        reach.update({k: {p: c / float(n) for p, c in v.items()} for k, v in reached.items()})
        reach["finals"] = {pair: c / float(n) for pair, c in finals.items()}
        reach["next"] = {mid: {p: c / float(n) for p, c in v.items()} for mid, v in nxt.items()}
    return {p: c / float(n) for p, c in wins.items()}


def seeded_draw(ranked, size, rng):
    """A random draw that follows seeding rules: 1 and 2 at opposite ends, 3-4 in the other quarters,
    5-8 one per quarter, 9-16 one per eighth; everyone else anywhere. Returns slots in bracket order."""
    slots = [None] * size
    q, e = size // 4, size // 8
    def place(players, starts):
        rng.shuffle(starts)
        for p, at in zip(players, starts):
            slots[at] = p
    place(ranked[:1], [0])                      # 1: top of the draw
    place(ranked[1:2], [size - 1])              # 2: bottom, so 1 and 2 can only meet in the final
    place(ranked[2:4], [2 * q - 1, 2 * q])      # 3 and 4: one in each half, in the quarters without 1 or 2
    place(ranked[4:8], [q - 1, q, 3 * q - 1, 3 * q])  # 5-8: one per quarter, at the end away from its top seed
    place(ranked[8:16], [i * e + (e - 1 if i % 2 == 0 else 0) for i in range(8)])  # 9-16: one per eighth
    rest = [p for p in ranked[16:size]]
    open_ = [i for i in range(size) if slots[i] is None]
    rng.shuffle(rest)
    for i, p in zip(open_, rest):
        slots[i] = p
    return slots


def simulate_projected(ranked, ratings, best_of_5, n, seed, size=64, reach=None):
    """Title odds before the draw is out: a fresh seeded draw of the top `size` players in every run."""
    rng = random.Random(seed)
    ranked = ranked[:size]
    if len(ranked) < 8:
        return {}
    size = 1 << (len(ranked).bit_length() - 1)  # largest power of two that fits
    ranked = ranked[:size]
    default = sorted(ratings.values())[len(ratings) // 5] if ratings else 1500.0
    cache = {}
    def beats(a, b):
        if (a, b) not in cache:
            p = win_prob(ratings.get(a, default), ratings.get(b, default))
            cache[(a, b)] = best_of_five(p) if best_of_5 else p
        return rng.random() < cache[(a, b)]
    wins = defaultdict(int)
    reached = {k: defaultdict(int) for k in ("qf", "sf", "f")}
    finals = defaultdict(int)
    for _ in range(n):
        field = seeded_draw(ranked, size, rng)
        while len(field) > 1:
            k = {8: "qf", 4: "sf", 2: "f"}.get(len(field))
            if k:
                for p in field:
                    reached[k][p] += 1
            if len(field) == 2:
                finals[tuple(sorted(field))] += 1
            field = [a if beats(a, b) else b for a, b in zip(field[::2], field[1::2])]
        wins[field[0]] += 1
    if reach is not None:
        reach.update({k: {p: c / float(n) for p, c in v.items()} for k, v in reached.items()})
        reach["finals"] = {pair: c / float(n) for pair, c in finals.items()}
    return {p: c / float(n) for p, c in wins.items()}


# ---------------------------------------------------------------- season finales (round robin)

GROUP_STAGE = "group stage"


def is_group_match(m):
    return (m.get("round") or "").lower().startswith("group")


def rr_groups(matches):
    """Groups from who has played (or is scheduled to play) whom, in order of first match.

    ESPN doesn't name the groups, so they're the connected parts of the group-stage match graph.
    Early on (one match per player listed) there can be more than two parts.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    order = []
    for m in sorted((m for m in matches if is_group_match(m)), key=lambda m: m["date"] or ""):
        for p in (m["a"], m["b"]):
            if p and p not in order:
                order.append(p)
        if m["a"] and m["b"]:
            parent[find(m["a"])] = find(m["b"])
    comps = {}
    for p in order:
        comps.setdefault(find(p), []).append(p)
    return list(comps.values())


def as_of_rr(event, d):
    """A finale as it stood at the end of day d."""
    ms = [dict(m) for m in event["matches"] if not (m["round"] or "").lower().startswith("qual")]
    done = lambda m: m["status"] in ("final", "retired", "walkover") and day(m["date"]) <= d
    groups_done = all(done(m) for m in ms if is_group_match(m))
    semis_done = all(done(m) for m in ms if (m["round"] or "").lower().startswith("semi"))
    for m in ms:
        if done(m):
            continue
        m["status"], m["w"] = "scheduled", None
        r = (m["round"] or "").lower()
        if (r.startswith("semi") and not groups_done) or (r == "final" and not semis_done):
            m["a"] = m["b"] = None
            m["an"] = m["bn"] = "TBD"
    return ms


def _standings(players, results, rng):
    """Order a group as the tours do: most wins; two players level on wins split by head-to-head;
    three or more level split by the share of sets won (then at random).

    results: (winner, loser) or (winner, loser, (sets won by winner, sets won by loser)).
    """
    wins = {p: 0 for p in players}
    sets = {p: [0, 0] for p in players}  # sets won, sets played
    h2h = {}
    for r in results:
        w, l = r[0], r[1]
        if w in wins:
            wins[w] += 1
        h2h[(w, l)] = True
        if len(r) > 2 and r[2]:
            for p, won in ((w, r[2][0]), (l, r[2][1])):
                if p in sets:
                    sets[p][0] += won
                    sets[p][1] += r[2][0] + r[2][1]
    level = {}
    for p in players:
        level.setdefault(wins[p], []).append(p)
    share = lambda p: sets[p][0] / float(sets[p][1]) if sets[p][1] else 0.0
    order = sorted(players, key=lambda p: (-wins[p], -share(p) if len(level[wins[p]]) >= 3 else 0, rng.random()))
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        level = [p for p in order if wins[p] == wins[a]]
        if wins[a] == wins[b] and len(level) == 2 and h2h.get((b, a)):
            order[i], order[i + 1] = b, a
    return order


def simulate_finals(matches, ratings, n, seed, projected=None, finals=None):
    """Monte Carlo for a season finale. Returns ({player: P(title)}, {player: P(reach semis)}).
    Pass a dict as `finals` to also get {(player, player): P(that pair contests the final)}.

    projected: ranked list of 8 player ids to use before ESPN publishes the groups. The draw then
    follows the tours' rules: seeds 1 and 2 apart, and 3/4, 5/6 and 7/8 each split between the groups.
    """
    rng = random.Random(seed)
    known = list(ratings.values())
    default = sorted(known)[len(known) // 5] if known else 1500.0
    cache = {}

    def beats(a, b):
        if (a, b) not in cache:
            cache[(a, b)] = win_prob(ratings.get(a, default), ratings.get(b, default))
        return rng.random() < cache[(a, b)]

    def play_sets(a, b):
        """A best-of-3 group match set by set: (winner, loser, (sets won by winner, by loser))."""
        if ("s", a, b) not in cache:
            cache[("s", a, b)] = set_prob(win_prob(ratings.get(a, default), ratings.get(b, default)))
        s, won = cache[("s", a, b)], [0, 0]
        while max(won) < 2:
            won[0 if rng.random() < s else 1] += 1
        return (a, b, tuple(won)) if won[0] == 2 else (b, a, (won[1], won[0]))

    group_ms = [m for m in matches if is_group_match(m) and m["a"] and m["b"]]
    semis = [m for m in matches if (m["round"] or "").lower().startswith("semi")]
    final = [m for m in matches if (m["round"] or "").lower() == "final"]
    comps = rr_groups(matches)
    use_projection = projected is not None and not group_ms

    def finished(m):
        return m["status"] in ("final", "retired", "walkover") and m["w"] is not None and m["a"] and m["b"]

    def winner(m, a=None, b=None):
        a, b = a or m["a"], b or m["b"]
        if m is not None and finished(m):
            return m["a"] if m["w"] == 0 else m["b"]
        return a if beats(a, b) else b

    titles, semis_reached, final_pairs = defaultdict(int), defaultdict(int), defaultdict(int)
    for _ in range(n):
        if use_projection:
            ga, gb = [projected[0]], [projected[1]]
            for i in (2, 4, 6):
                pair = projected[i:i + 2]
                rng.shuffle(pair)
                ga.append(pair[0])
                if len(pair) > 1:
                    gb.append(pair[1])
            groups = [ga, gb]
        elif len(comps) > 2:  # groups not fully known yet: join the pieces at random into two groups
            pieces = comps[:]
            rng.shuffle(pieces)
            groups = [[], []]
            for piece in pieces:
                groups[0 if len(groups[0]) < 4 else 1].extend(piece)
        else:
            groups = [g[:] for g in comps]
        top = []
        for g in groups:
            listed = [m for m in group_ms if m["a"] in g and m["b"] in g]
            pairs = {frozenset((m["a"], m["b"])) for m in listed}
            results = []
            for m in listed:
                if finished(m):
                    w = m["a"] if m["w"] == 0 else m["b"]
                    sa, sb = sets_won(m.get("sc"))
                    results.append((w, m["b"] if w == m["a"] else m["a"], (sa, sb) if m["w"] == 0 else (sb, sa)))
                else:
                    results.append(play_sets(m["a"], m["b"]))
            if len(g) == 4:  # every pair meets once; simulate pairings ESPN hasn't listed yet
                for i in range(4):
                    for j in range(i + 1, 4):
                        if frozenset((g[i], g[j])) not in pairs:
                            results.append(play_sets(g[i], g[j]))
            top.append(_standings(g, results, rng)[:2])
        if len(top) < 2 or any(len(t) < 2 for t in top):
            continue
        real_semis = [m for m in semis if m["a"] and m["b"]]
        if len(real_semis) == 2:
            pairings = [(m, m["a"], m["b"]) for m in real_semis]
        else:  # group winner meets the other group's runner-up
            pairings = [(None, top[0][0], top[1][1]), (None, top[1][0], top[0][1])]
        finalists = []
        for m, a, b in pairings:
            semis_reached[a] += 1
            semis_reached[b] += 1
            finalists.append(winner(m, a, b) if m is not None else (a if beats(a, b) else b))
        f = final[0] if final and final[0]["a"] and final[0]["b"] else None
        final_pairs[tuple(sorted((f["a"], f["b"]) if f is not None else finalists))] += 1
        champ = winner(f) if f is not None else (finalists[0] if beats(finalists[0], finalists[1]) else finalists[1])
        titles[champ] += 1
    if finals is not None:
        finals.update({pair: c / float(n) for pair, c in final_pairs.items()})
    return ({p: c / float(n) for p, c in titles.items()},
            {p: c / float(n) for p, c in semis_reached.items()})
