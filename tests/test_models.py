"""Unit tests for the rating models and simulators (no network needed)."""
import unittest

import numpy as np

from pipeline.soccer_model import Elo, GoalsModel, fit_goals_model, gd_multiplier, score_predictions
from pipeline.soccer_sim import Matchups, knockout_state, sim_table, simulate_league
from pipeline.tennis_model import as_of, best_of_five, round_rank, simulate_draw, win_prob


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


if __name__ == "__main__":
    unittest.main()
