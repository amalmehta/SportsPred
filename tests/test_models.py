"""Unit tests for the rating models and simulators (no network needed)."""
import unittest

import numpy as np

from pipeline.soccer_model import Elo, GoalsModel, fit_goals_model, gd_multiplier, score_predictions
from pipeline.soccer_sim import Matchups, knockout_state, sim_table, simulate_league
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


if __name__ == "__main__":
    unittest.main()
