"""Unit tests for the rating models and simulators (no network needed)."""
import unittest

import numpy as np

from pipeline.soccer_model import Elo, GoalsModel, fit_goals_model, gd_multiplier, score_predictions
from pipeline.soccer_sim import Matchups, knockout_state, sim_table, simulate_league, simulate_qualifying
from pipeline.tennis_model import (TennisElo, _standings, as_of, as_of_rr, best_of_five, fit_surface_weight, round_rank,
                                   rr_groups, simulate_draw, simulate_finals, surface_of, win_prob)


class SoccerModelTests(unittest.TestCase):
    def test_outcome_probs_sum_to_one_and_follow_gap(self):
        gm = GoalsModel()
        weak = gm.outcome_probs(-200)
        even = gm.outcome_probs(0)
        strong = gm.outcome_probs(200)
        for p in (weak, even, strong):
            self.assertAlmostEqual(sum(p[:3]), 1.0, places=6)
        self.assertLess(weak[0], even[0])
        self.assertLess(even[0], strong[0])
        self.assertAlmostEqual(even[0], even[2], places=6)

    def test_elo_is_zero_sum(self):
        elo = Elo()
        elo.update({"id": "1", "date": "2024-01-01", "home": "A", "away": "B", "hg": 3, "ag": 0, "neutral": False})
        self.assertAlmostEqual(elo.ratings["A"] + elo.ratings["B"], 3000.0, places=6)
        self.assertGreater(elo.ratings["A"], 1500)

    def test_goal_difference_multiplier(self):
        self.assertEqual(gd_multiplier(1), 1.0)
        self.assertEqual(gd_multiplier(-2), 1.5)
        self.assertGreater(gd_multiplier(4), gd_multiplier(3))

    def test_elo_snapshots_are_taken_before_later_days(self):
        elo = Elo()
        ms = [{"id": str(i), "date": "2024-01-0%dT15:00Z" % (i + 1), "home": "A", "away": "B", "hg": 1, "ag": 0,
               "neutral": True} for i in range(3)]
        snaps = elo.run(ms, ["2024-01-01", "2024-01-02"])
        self.assertLess(snaps["2024-01-01"]["A"], snaps["2024-01-02"]["A"])
        self.assertLess(snaps["2024-01-02"]["A"], elo.ratings["A"])

    def test_fit_recovers_slope(self):
        rng = np.random.default_rng(1)
        true = GoalsModel(np.log(1.4), 0.9)
        samples = []
        for gap in rng.uniform(-400, 400, 6000):
            lh, la = true.lambdas(gap)
            samples.append((gap, rng.poisson(lh), rng.poisson(la)))
        fit = fit_goals_model(samples)
        self.assertAlmostEqual(fit.slope, 0.9, delta=0.1)

    def test_score_predictions(self):
        s = score_predictions([(0.6, 0.2, 0.2, 0), (0.2, 0.2, 0.6, 0)])
        self.assertEqual(s["n"], 2)
        self.assertAlmostEqual(s["accuracy"], 0.5)


class SoccerSimTests(unittest.TestCase):
    def setUp(self):
        self.mu = Matchups({"A": 1800, "B": 1500, "C": 1500, "D": 1200}, GoalsModel(), 60)

    def test_finished_table_has_no_uncertainty(self):
        res = simulate_league(["A", "B"], [("A", "B", 2, 0), ("B", "A", 0, 1)], [], self.mu, 200, 1)
        self.assertEqual(res["p_win"]["A"], 1.0)
        self.assertEqual(res["proj_pts"]["A"], 6.0)

    def test_stronger_team_wins_more_often(self):
        teams = ["A", "B", "C", "D"]
        fixtures = [(h, a, False) for h in teams for a in teams if h != a]
        res = simulate_league(teams, [], fixtures, self.mu, 2000, 2)
        self.assertAlmostEqual(sum(res["p_win"].values()), 1.0, places=6)
        self.assertGreater(res["p_win"]["A"], res["p_win"]["B"])
        self.assertGreater(res["p_win"]["B"], res["p_win"]["D"])

    def test_table_order_breaks_ties_on_goal_difference(self):
        order, _ = sim_table(["X", "Y"], [("X", "Z", 1, 0), ("Y", "Z", 5, 0)], [], self.mu, 10, np.random.default_rng(0))
        self.assertTrue((order[:, 0] == 1).all())

    def test_tie_probabilities(self):
        mu = Matchups({"A": 1500, "B": 1500}, GoalsModel(), 60)
        self.assertAlmostEqual(mu.tie_prob("A", "B", (("A", "B", True),)), 0.5, places=6)
        two = (("A", "B", False), ("B", "A", False))
        self.assertAlmostEqual(mu.tie_prob("A", "B", two), 0.5, places=6)
        self.assertGreater(mu.tie_prob("A", "B", (("B", "A", False),), agg=3), 0.9)

    def test_qualifying_places(self):
        teams = ["A", "B", "C", "D"]
        fixtures = [(h, a, False) for h in teams for a in teams if h != a]
        res = simulate_qualifying({"Group 1": teams}, [], fixtures, self.mu, 3000, 5, direct=1, nxt=2)
        for key, total in (("p_win", 1.0), ("p_qualify", 1.0), ("p_playoff", 2.0)):
            self.assertAlmostEqual(sum(res[key].values()), total, places=6)
        self.assertEqual(res["p_win"], res["p_qualify"])  # one direct place = topping the group
        self.assertGreater(res["p_qualify"]["A"], res["p_qualify"]["D"])
        done = simulate_qualifying({"G": ["A", "B"]}, [("D", "A", 3, 0)], [], self.mu, 100, 1, direct=1, nxt=1)
        self.assertEqual(sum(done["p_qualify"].values()), 1.0)  # results from outside the group are ignored

    def test_knockout_state_uses_aggregate(self):
        def m(h, a, hg=None, ag=None, status="final"):
            return {"date": "2027-02-0%d" % (1 if hg is not None else 2), "stage": "round-of-16", "home": h, "away": a,
                    "home_key": h, "away_key": a, "hg": hg, "ag": ag, "status": status, "neutral": False}
        ko = [m("A", "B", 1, 0), m("B", "A", 1, 0), m("C", "D", 3, 0), m("D", "C", status="scheduled")]
        ko[1]["winner"] = "home"  # B won the shoot-out
        stage, decided, open_ties = knockout_state(ko)
        self.assertEqual(stage, "round-of-16")
        self.assertEqual(decided, ["B"])
        self.assertEqual(open_ties[0][:2], ("C", "D"))
        self.assertEqual(open_ties[0][3], 3)


class TennisTests(unittest.TestCase):
    def test_best_of_five_helps_the_favourite(self):
        self.assertAlmostEqual(best_of_five(0.5), 0.5, places=6)
        self.assertGreater(best_of_five(0.7), 0.7)
        self.assertLess(best_of_five(0.3), 0.3)
        self.assertAlmostEqual(win_prob(1600, 1600), 0.5)

    def test_round_order(self):
        names = ["Final", "Round 2", "Quarterfinal", "Round 1", "Semifinal", "Qualifying Final"]
        self.assertEqual(sorted(names, key=round_rank),
                         ["Qualifying Final", "Round 1", "Round 2", "Quarterfinal", "Semifinal", "Final"])

    def draw(self):
        def m(i, rnd, a, b, w=None, status="final", d="2026-10-01"):
            return {"id": i, "round": rnd, "date": d + "T10:00Z", "status": status if w is not None else "scheduled",
                    "a": a, "an": a or "TBD", "b": b, "bn": b or "TBD", "w": w}
        return {"id": "t", "matches": [
            m("1", "Semifinal", "P1", "P2", 0), m("2", "Semifinal", "P3", "P4", None),
            m("3", "Final", "P1", None, None, d="2026-10-03"),
        ]}

    def test_simulate_draw_with_open_slot(self):
        ev = self.draw()
        from pipeline.tennis_model import main_draw
        probs = simulate_draw(main_draw(ev), {"P1": 1700, "P2": 1500, "P3": 1500, "P4": 1500}, False, 3000, 1)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=6)
        self.assertNotIn("P2", probs)  # P2 lost the semi
        self.assertGreater(probs["P1"], 0.5)

    def test_as_of_undoes_later_results(self):
        ev = self.draw()
        ev["matches"][0]["date"] = "2026-10-02T10:00Z"
        rounds = as_of(ev, "2026-10-01")
        semi = rounds[0][1][0]
        final = rounds[1][1][0]
        self.assertEqual(semi["status"], "scheduled")
        self.assertIsNone(final["a"])  # P1 hadn't reached the final yet


class SurfaceTests(unittest.TestCase):
    TABLE = {"clay": ["Roland Garros"], "grass": ["Wimbledon"]}

    def match(self, i, surface, winner="A"):
        return {"id": str(i), "date": "2025-01-%02dT10:00Z" % (i + 1), "a": winner, "an": winner,
                "b": "B" if winner == "A" else "A", "bn": "", "w": 0, "surface": surface}

    def test_surface_lookup(self):
        self.assertEqual(surface_of("Roland Garros", self.TABLE), "clay")
        self.assertEqual(surface_of("The Wimbledon Championships", self.TABLE), "grass")
        self.assertEqual(surface_of("US Open", self.TABLE), "hard")

    def test_surface_ratings_only_move_on_their_surface(self):
        elo = TennisElo(weight=0.5)
        elo.run([self.match(i, "clay") for i in range(5)])
        self.assertGreater(elo.surf["clay"]["A"], 1500)
        self.assertNotIn("A", elo.surf["grass"])
        self.assertGreater(elo.rating("A", "clay"), elo.rating("A", "grass"))
        elo.weight = 0.0
        self.assertAlmostEqual(elo.rating("A", "grass"), elo.rating("A"))

    def test_fit_prefers_surface_when_results_split_by_surface(self):
        elo = TennisElo()
        ms = []
        for i in range(30):  # A always wins on clay, B always wins on grass
            ms.append(self.match(2 * i, "clay", "A"))
            ms.append(self.match(2 * i + 1, "grass", "B"))
        for k, m in enumerate(ms):
            m["date"] = "2025-%02d-%02dT10:00Z" % (1 + k // 28, 1 + k % 28)
        elo.run(ms)
        self.assertGreaterEqual(fit_surface_weight(elo, ms[20:]), 0.8)


class FinalsTests(unittest.TestCase):
    """Season finales: two round-robin groups of four, top two reach the semis."""

    def m(self, i, rnd, a, b, w=None, d="2025-11-09"):
        return {"id": str(i), "round": rnd, "date": d + "T13:00Z", "status": "final" if w is not None else "scheduled",
                "a": a, "an": a or "TBD", "b": b, "bn": b or "TBD", "w": w}

    def event(self):
        A, B = ["A1", "A2", "A3", "A4"], ["B1", "B2", "B3", "B4"]
        ms, i = [], 0
        for g in (A, B):
            for x in range(4):
                for y in range(x + 1, 4):
                    i += 1
                    # day 1 results only; the stronger seed (lower number) wins
                    ms.append(self.m(i, "Group Stage", g[x], g[y], 0 if i in (1, 7) else None,
                                     "2025-11-09" if i in (1, 7) else "2025-11-11"))
        ms += [self.m(20, "Semifinal", None, None, d="2025-11-14"), self.m(21, "Semifinal", None, None, d="2025-11-14"),
               self.m(22, "Final", None, None, d="2025-11-15")]
        return {"id": "f", "matches": ms}

    def test_groups_come_from_the_match_graph(self):
        groups = rr_groups(self.event()["matches"])
        self.assertEqual([sorted(g) for g in groups], [["A1", "A2", "A3", "A4"], ["B1", "B2", "B3", "B4"]])

    def test_two_way_tie_goes_to_head_to_head(self):
        import random
        order = _standings(["X", "Y", "Z"], [("Y", "X"), ("X", "Z"), ("Y", "Z")], random.Random(0))
        self.assertEqual(order[0], "Y")
        order = _standings(["X", "Y", "Z", "W"], [("X", "Y"), ("Y", "Z"), ("Z", "W"), ("X", "W"), ("Y", "W"), ("Z", "X")],
                           random.Random(0))
        self.assertEqual(order[-1], "W")

    def test_simulate_finals_probabilities(self):
        ratings = {p: 1500 for p in ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4"]}
        ratings["A1"] = 1900
        title, semis = simulate_finals(self.event()["matches"], ratings, 3000, 3)
        self.assertAlmostEqual(sum(title.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(semis.values()), 4.0, places=6)
        self.assertEqual(max(title, key=title.get), "A1")

    def test_projected_field_keeps_top_two_seeds_apart(self):
        field = ["S%d" % i for i in range(1, 9)]
        ratings = {p: 2400 if p in ("S1", "S2") else 1200 for p in field}
        title, semis = simulate_finals([], ratings, 2000, 4, projected=field)
        self.assertAlmostEqual(semis["S1"], 1.0, places=6)  # both giants always reach the semis
        self.assertAlmostEqual(semis["S2"], 1.0, places=6)
        self.assertGreater(title["S1"] + title["S2"], 0.99)

    def test_as_of_rr_hides_knockout_players_until_groups_finish(self):
        ev = self.event()
        ev["matches"][-3].update(a="A1", an="A1", b="B2", bn="B2", w=0, status="final")
        rolled = as_of_rr(ev, "2025-11-10")
        semi = [m for m in rolled if m["id"] == "20"][0]
        self.assertIsNone(semi["a"])
        self.assertEqual(semi["status"], "scheduled")


class LiveLogTests(unittest.TestCase):
    def test_merge_keeps_latest_per_day_and_current_season(self):
        from pipeline.live_log import merge
        entries = [
            {"date": "2026-10-12", "t": "2026-10-12T06:00Z", "season": "2026–27", "p": {"A": 0.5}},
            {"date": "2026-10-12", "t": "2026-10-12T21:00Z", "season": "2026–27", "p": {"A": 0.6}},
            {"date": "2026-10-11", "t": "2026-10-11T21:00Z", "season": "2026–27", "p": {"A": 0.4}},
            {"date": "2026-05-01", "t": "2026-05-01T21:00Z", "season": "2025–26", "p": {"A": 0.9}},
        ]
        out = merge(entries, "2026–27")
        self.assertEqual([e["date"] for e in out], ["2026-10-11", "2026-10-12"])
        self.assertEqual(out[1]["p"]["A"], 0.6)

    def test_headline_follows_the_competition(self):
        from pipeline.live_log import headline
        league = {"sport": "soccer", "format": "league", "table": [{"team": "A", "p_win": 0.7}, {"team": "B", "p_win": 0.0}]}
        quals = {"sport": "soccer", "format": "qualifying",
                 "table": [{"team": "A", "p_win": 0.2, "p_qualify": 0.9}]}
        draw = {"sport": "tennis", "format": "knockout", "table": [{"player": "P", "p_win": 0.3}]}
        self.assertEqual(headline(league), {"A": 0.7})
        self.assertEqual(headline(quals), {"A": 0.9})
        self.assertEqual(headline(draw), {"P": 0.3})


class PublishCheckTests(unittest.TestCase):
    def test_good_and_bad_files(self):
        from pipeline.check import problems_in
        good = {"name": "L", "sport": "soccer", "format": "league", "favourite": {"name": "A"},
                "table": [{"team": "A", "p_win": 0.6}, {"team": "B", "p_win": 0.4}],
                "upcoming": [{"home": "A", "away": "B", "p": [0.5, 0.3, 0.2]}]}
        self.assertEqual(problems_in(good), [])
        bad = dict(good, table=[{"team": "A", "p_win": 0.6}, {"team": "B", "p_win": 0.1}])
        self.assertTrue(problems_in(bad))
        self.assertTrue(problems_in(dict(good, table=[])))
        self.assertTrue(problems_in(dict(good, upcoming=[{"home": "A", "away": "B", "p": [0.9, 0.3, 0.2]}])))
        awaiting = {"name": "T", "sport": "tennis", "favourite": None, "table": [], "upcoming": []}
        self.assertEqual(problems_in(awaiting), [])
        quals = {"name": "Q", "sport": "soccer", "format": "qualifying", "slots": {"direct": 1},
                 "table": [{"team": t, "group": g, "p_win": 0.5, "p_qualify": 0.5, "p_playoff": 0.5}
                           for g in ("A", "B") for t in (g + "1", g + "2")]}
        self.assertEqual(problems_in(quals), [])


class CalibrationTests(unittest.TestCase):
    def test_bins_and_record(self):
        from pipeline.common import calibration, track_record
        pairs = [(0.75, 1)] * 30 + [(0.75, 0)] * 10 + [(0.15, 0)] * 5
        rows = calibration(pairs)
        self.assertEqual(len(rows), 1)  # the 10-20% band has too few predictions to show
        self.assertAlmostEqual(rows[0]["p"], 0.75)
        self.assertAlmostEqual(rows[0]["freq"], 0.75)
        self.assertEqual(rows[0]["n"], 40)
        self.assertEqual(calibration([(1.0, 1)] * 20)[0]["hi"], 1.0)  # p = 1 lands in the top band
        self.assertEqual(track_record([(True, 0.1), (False, 0.5)]), {"n": 2, "called": 1, "brier": 0.3})
        self.assertIsNone(track_record([]))


class DigestTests(unittest.TestCase):
    def test_today_digest_picks_soon_matches_and_big_moves(self):
        import os, tempfile
        from datetime import datetime, timedelta, timezone
        from pipeline import build
        from pipeline.common import write_json
        iso = lambda h: (datetime.now(timezone.utc) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%MZ")
        comp = {"id": "x.1", "sport": "soccer", "name": "Test League", "group": "domestic", "table": [],
                "upcoming": [{"date": iso(5), "home": "A", "away": "B", "p": [0.5, 0.3, 0.2]},
                             {"date": iso(100), "home": "C", "away": "D", "p": [0.4, 0.3, 0.3]}],
                "live": [{"date": "2026-10-16", "p": {"A": 0.50, "B": 0.30}},
                         {"date": "2026-10-17", "p": {"A": 0.60, "B": 0.29}}]}
        with tempfile.TemporaryDirectory() as tmp:
            old = build.SITE_DATA_DIR
            build.SITE_DATA_DIR = tmp
            try:
                write_json(os.path.join(tmp, "soccer", "x.1.json"), comp)
                d = build.today_digest([{"id": "x.1", "sport": "soccer"}])
            finally:
                build.SITE_DATA_DIR = old
        self.assertEqual([m["home"] for m in d["matches"]], ["A"])          # only the next day and a half
        self.assertEqual([(m["team"], m["after"]) for m in d["movers"]], [("A", 0.60)])  # B moved < 3 points


if __name__ == "__main__":
    unittest.main()
