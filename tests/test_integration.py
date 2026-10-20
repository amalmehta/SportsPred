"""End-to-end tests on synthetic data (no network): a whole competition file is built, written and
passed through the publish check, the way the real pipeline does it."""
import os
import random
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from pipeline import check, config, live_log, soccer_build, title_backtest as tb
from pipeline.common import write_json
from pipeline.soccer_model import Elo, GoalsModel
from pipeline.soccer_sim import Matchups, real_ties, uefa_knockout
from pipeline.tennis_build import event_payload
from pipeline.tennis_model import TennisElo

TODAY = "2026-10-20"


def league_matches(teams, start="2026-08-15", played_rounds=3, seed=1):
    """A double round robin: the first rounds finished (stronger names win more), the rest scheduled."""
    rng = random.Random(seed)
    strength = {t: len(teams) - i for i, t in enumerate(teams)}
    pairs = [(h, a) for h in teams for a in teams if h != a]
    rng.shuffle(pairs)
    per_round = len(teams) // 2
    d0 = date.fromisoformat(start)
    out = []
    for i, (h, a) in enumerate(pairs):
        rnd = i // per_round
        m = {"id": "m%d" % i, "slug": "test.1", "date": (d0 + timedelta(days=7 * rnd)).isoformat() + "T15:00Z",
             "season": 2026, "stage": "2026-27-test-league", "home_key": h, "away_key": a, "home": h, "away": a,
             "home_id": h, "away_id": a, "neutral": False, "status": "scheduled"}
        if rnd < played_rounds:
            hg = rng.randint(0, 2) + (1 if strength[h] > strength[a] else 0)
            ag = rng.randint(0, 2) + (1 if strength[a] > strength[h] else 0)
            m.update(status="final", hg=hg, ag=ag, winner="home" if hg > ag else ("away" if ag > hg else "draw"))
        out.append(m)
    return out


class SoccerPipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"slug": "test.1", "name": "Test League", "country": "Testland", "format": "league",
                    "group": "domestic", "top": 2, "drop": 1}
        self.teams = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
        self.matches = league_matches(self.teams)

    def payload(self):
        fin = [dict(m, home=m["home_key"], away=m["away_key"]) for m in self.matches if m["status"] == "final"]
        elo = Elo(hfa=60.0)
        snaps = elo.run(fin, soccer_build.replay_days(self.matches, TODAY))
        old = (config.SIMS_TODAY, config.SIMS_REPLAY)
        config.SIMS_TODAY, config.SIMS_REPLAY = 2000, 300
        try:
            return soccer_build.comp_payload(self.cfg, "domestic", self.matches, elo, GoalsModel(), snaps,
                                             {t: t for t in self.teams}, TODAY + "T12:00Z")
        finally:
            config.SIMS_TODAY, config.SIMS_REPLAY = old

    def test_competition_file_is_complete_and_consistent(self):
        c = self.payload()
        self.assertEqual(len(c["table"]), 6)
        self.assertAlmostEqual(sum(r["p_win"] for r in c["table"]), 1.0, places=2)
        self.assertAlmostEqual(sum(r["p_top"] for r in c["table"]), 2.0, places=2)
        self.assertAlmostEqual(sum(r["p_drop"] for r in c["table"]), 1.0, places=2)
        self.assertEqual(c["places"], {"top": 2, "drop": 1})
        self.assertEqual(c["history"]["dates"][-1], TODAY)
        self.assertGreater(len(c["history"]["dates"]), 2)  # pre-season + match days + today
        self.assertTrue(all(abs(sum(m["p"]) - 1) < 0.01 for m in c["upcoming"]))
        self.assertEqual(c["record"]["n"], len([m for m in self.matches if m["status"] == "final"]))
        self.assertEqual(c["status"], "live")

    def test_publish_check_accepts_a_real_build_and_rejects_a_broken_one(self):
        c = self.payload()
        with tempfile.TemporaryDirectory() as tmp:
            write_json(os.path.join(tmp, "soccer", "test.1.json"), c)
            write_json(os.path.join(tmp, "tennis", "t.json"), {"name": "T", "sport": "tennis", "table": [], "upcoming": []})
            for extra in ("search.json", "today.json", "model.json"):
                write_json(os.path.join(tmp, extra), {})
            write_json(os.path.join(tmp, "index.json"), {"competitions": [
                {"id": "test.1", "sport": "soccer"}, {"id": "t", "sport": "tennis"}]})
            self.assertEqual(check.check(tmp, compare_live=False), [])
            c["table"][0]["p_win"] += 0.2
            write_json(os.path.join(tmp, "soccer", "test.1.json"), c)
            self.assertTrue(check.check(tmp, compare_live=False))

    def test_failed_fetch_keeps_last_good_copy_and_skips_the_log(self):
        good = {"id": "test.1", "sport": "soccer", "updated": "2026-10-19T10:00Z", "season": "2026–27",
                "table": [{"team": "Alpha", "p_win": 1.0}], "live": [{"date": "2026-10-19", "season": "2026–27", "p": {}}]}
        with mock.patch.object(live_log, "previous_file", return_value=good):
            old = live_log.stale_copy("soccer", "test.1", "ESPN didn't answer")
        self.assertTrue(old["stale"])
        self.assertEqual(old["updated"], good["updated"])  # the page shows when it was really from
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SPORTSPRED_TODAY", None)
            live_log.attach([old], TODAY)
        self.assertEqual(len(old["live"]), 1)  # no fake entry for today


class UefaKnockoutTests(unittest.TestCase):
    def setUp(self):
        self.ranked = ["T%02d" % i for i in range(1, 37)]
        ratings = {t: 2000 - 15 * i for i, t in enumerate(self.ranked)}
        self.mu = Matchups(ratings, GoalsModel(), 60)

    def ko(self, rnd_stage, a, b, hg, ag, d, status="final"):
        m = {"date": d, "stage": rnd_stage, "home": a, "away": b, "home_key": a, "away_key": b, "neutral": False,
             "status": status}
        if status == "final":
            m.update(hg=hg, ag=ag, winner="home" if hg > ag else ("away" if ag > hg else "draw"))
        return m

    def test_seeds_one_and_two_only_meet_in_the_final_and_real_results_stick(self):
        # T09 (9th) lost its real playoff tie to T24 on aggregate: T09 can never win
        ko = [self.ko("knockout-round-playoffs", "T24", "T09", 2, 0, "2027-02-10T20:00Z"),
              self.ko("knockout-round-playoffs", "T09", "T24", 1, 1, "2027-02-17T20:00Z")]
        ties = real_ties(ko)
        rng = random.Random(3)
        champs = [uefa_knockout(self.ranked, ties, self.mu, rng) for _ in range(400)]
        self.assertNotIn("T09", champs)
        self.assertIn("T01", champs)

    def test_a_finished_knockout_always_gives_the_real_champion(self):
        # a full real knockout; the quarter-final draw differs from the model's own bracket on purpose
        rounds = [("knockout-round-playoffs", [("T15", "T18"), ("T16", "T17"), ("T13", "T20"), ("T14", "T19"),
                                              ("T11", "T22"), ("T12", "T21"), ("T09", "T24"), ("T10", "T23")]),
                  ("round-of-16", [("T01", "T16"), ("T02", "T15"), ("T03", "T14"), ("T04", "T13"),
                                   ("T05", "T12"), ("T06", "T11"), ("T07", "T10"), ("T08", "T09")]),
                  ("quarterfinals", [("T05", "T01"), ("T08", "T04"), ("T02", "T07"), ("T06", "T03")]),
                  ("semifinals", [("T08", "T05"), ("T02", "T06")]),
                  ("final", [("T08", "T02")])]
        ko, day = [], 0
        for stage, pairs in rounds:  # the first-named side wins 1-0 at home
            day += 7
            ko.extend(self.ko(stage, a, b, 1, 0, "2027-02-%02dT20:00Z" % min(day, 28)) for a, b in pairs)
        ties = real_ties(ko)
        rng = random.Random(4)
        self.assertEqual({uefa_knockout(self.ranked, ties, self.mu, rng) for _ in range(200)}, {"T08"})


class TennisPipelineTests(unittest.TestCase):
    def test_event_file_from_a_partly_played_draw(self):
        players = ["P%d" % i for i in range(1, 9)]
        def m(i, rnd, a, b, w, d):
            return {"id": str(i), "round": rnd, "date": d + "T10:00Z", "status": "final" if w is not None else "scheduled",
                    "a": a, "an": a or "TBD", "b": b, "bn": b or "TBD", "w": w}
        matches = [m(1, "Quarterfinal", "P1", "P8", 0, "2026-10-14"), m(2, "Quarterfinal", "P4", "P5", 1, "2026-10-14"),
                   m(3, "Quarterfinal", "P2", "P7", None, "2026-10-21"), m(4, "Quarterfinal", "P3", "P6", None, "2026-10-21"),
                   m(5, "Semifinal", "P1", "P5", None, "2026-10-22"), m(6, "Semifinal", None, None, None, "2026-10-22"),
                   m(7, "Final", None, None, None, "2026-10-23")]
        ev = {"id": "atp-test", "tour": "atp", "name": "Rolex Shanghai Masters", "start": "2026-10-13T04:00Z",
              "end": "2026-10-24T04:00Z", "major": False, "defending": None, "matches": matches}
        elo = TennisElo()
        history = [{"id": "h%d" % i, "date": "2026-09-0%dT10:00Z" % (1 + i % 9), "a": players[i % 4], "an": players[i % 4],
                    "b": players[4 + i % 4], "bn": players[4 + i % 4], "w": 0, "surface": "hard"} for i in range(20)]
        snaps = elo.run(history + [dict(x, surface="hard") for x in matches if x["status"] == "final"],
                        ["2026-10-13", "2026-10-14"])
        old = (config.SIMS_TODAY, config.SIMS_REPLAY)
        config.SIMS_TODAY, config.SIMS_REPLAY = 2000, 300
        try:
            c = event_payload(ev, "atp", elo, snaps, TODAY + "T12:00Z")
        finally:
            config.SIMS_TODAY, config.SIMS_REPLAY = old
        self.assertAlmostEqual(sum(r["p_win"] for r in c["table"]), 1.0, places=2)
        out = {r["player"] for r in c["table"] if not r["alive"]}
        self.assertEqual(out, {"P8", "P4"})
        self.assertEqual(c["status"], "live")
        self.assertEqual(c["record"]["n"], 2)
        self.assertEqual(check.problems_in(c), [])


class TitleBacktestTests(unittest.TestCase):
    def test_champions_and_grades(self):
        ms = [{"status": "final", "home_key": "A", "away_key": "B", "hg": 2, "ag": 0, "date": "x", "stage": "league"},
              {"status": "final", "home_key": "B", "away_key": "C", "hg": 1, "ag": 1, "date": "y", "stage": "league"}]
        self.assertEqual(tb.league_champion(ms), "A")
        final = [{"status": "final", "home_key": "A", "away_key": "B", "hg": 1, "ag": 1, "winner": "away", "date": "z", "stage": "final"}]
        self.assertEqual(tb.cup_champion(final), "B")  # won on penalties
        row = tb.grade("L", "2025", {"A": 0.5, "B": 0.3, "C": 0.2}, "B")
        self.assertEqual((row["rank"], row["favourite"], row["field"]), (2, "A", 3))
        s = tb.summarise([row, tb.grade("L", "2026", {"A": 0.6, "B": 0.4}, "A")])
        self.assertEqual((s["n"], s["favourite_won"], s["winner_in_top3"]), (2, 1, 2))


class StampTests(unittest.TestCase):
    def test_asset_links_get_content_hashes(self):
        from pipeline.stamp import stamp
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "assets"))
            for name, body in (("app.js", "a"), ("app.css", "b")):
                with open(os.path.join(tmp, "assets", name), "w") as f:
                    f.write(body)
            page = os.path.join(tmp, "index.html")
            with open(page, "w") as f:
                f.write('<link href="assets/app.css"><script src="assets/app.js?v=old"></script><a href="how.html">')
            stamp(tmp)
            with open(page) as f:
                html = f.read()
            self.assertRegex(html, r'assets/app\.css\?v=[0-9a-f]{10}"')
            self.assertRegex(html, r'assets/app\.js\?v=[0-9a-f]{10}"')
            self.assertNotIn("v=old", html)
            self.assertIn('href="how.html"', html)  # pages themselves are untouched


class NewFeatureTests(unittest.TestCase):
    def test_title_swings_and_whatif_data(self):
        t = SoccerPipelineTests("test_competition_file_is_complete_and_consistent")
        t.setUp()
        c = t.payload()
        # the next games: home win / draw / away win shares add up, and conditional odds are probabilities
        for sw in c["swings"]:
            self.assertAlmostEqual(sum(sw["share"]), 1.0, places=2)
            self.assertTrue(all(v is None or 0 <= v <= 1 for vs in sw["if"].values() for v in vs))
            self.assertIn(sw["home"], t.teams)
        w = c["whatif"]
        self.assertEqual(len(w["teams"]), 6)
        self.assertEqual(len(w["fixtures"]), len([m for m in t.matches if m["status"] != "final"]))
        played = sum(b[0] for b in w["base"])
        self.assertEqual(played, sum(r["pts"] for r in c["table"]))  # table so far matches
        self.assertTrue(all("r" in m and "h2h" in m for m in c["upcoming"]))

    def test_team_pages_and_smoke_test(self):
        from pipeline import build, smoke
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data")
            comp = {"id": "x.1", "sport": "soccer", "name": "Test League", "group": "domestic", "status": "live",
                    "table": [{"team": "Alpha", "p_win": 0.7}, {"team": "Bravo", "p_win": 0.3}],
                    "upcoming": [{"date": "2026-10-25T15:00Z", "home": "Alpha", "away": "Bravo", "p": [0.5, 0.3, 0.2]}], "recent": []}
            write_json(os.path.join(data, "soccer", "x.1.json"), comp)
            old = build.SITE_DATA_DIR
            build.SITE_DATA_DIR = data
            try:
                pages = build.team_pages([{"id": "x.1", "sport": "soccer"}], {"clubs": {"Alpha": [["2026-10-01", 1600]]}},
                                         out_dir=os.path.join(data, "teams"))
            finally:
                build.SITE_DATA_DIR = old
            self.assertEqual(pages["Alpha|soccer"], "soccer-alpha")
            alpha = __import__("json").load(open(os.path.join(data, "teams", "soccer-alpha.json")))
            self.assertEqual((alpha["rating"], len(alpha["upcoming"])), ([["2026-10-01", 1600]], 1))
            write_json(os.path.join(data, "teams.json"), pages)
            write_json(os.path.join(data, "index.json"), {"competitions": [{"id": "x.1", "sport": "soccer"}]})
            with open(os.path.join(tmp, "index.html"), "w") as f:
                f.write('<link href="assets/app.css"><a href="https://example.com">x</a>')
            self.assertEqual(len(smoke.problems(tmp)), 1)  # assets/app.css is missing
            os.makedirs(os.path.join(tmp, "assets"))
            with open(os.path.join(tmp, "assets", "app.css"), "w") as f:
                f.write("body{}")
            self.assertEqual(smoke.problems(tmp), [])
        self.assertEqual(build.slug("Borussia Mönchengladbach"), "borussia-monchengladbach")


class RoundSixTests(unittest.TestCase):
    def test_seeded_draw_rules_and_projected_odds(self):
        from pipeline.tennis_model import seeded_draw, simulate_projected
        ranked = ["S%d" % i for i in range(1, 65)]
        rng = random.Random(7)
        for _ in range(100):
            pos = {p: i for i, p in enumerate(seeded_draw(ranked, 64, rng))}
            self.assertEqual(len(pos), 64)
            self.assertNotEqual(pos["S1"] // 32, pos["S2"] // 32)           # 1 and 2 in different halves
            self.assertEqual(len({pos["S%d" % i] // 16 for i in range(1, 5)}), 4)  # top 4 in different quarters
            self.assertEqual(len({pos["S%d" % i] // 8 for i in range(1, 17)}), 8)  # top 16 cover all 8 eighths, 2 seeds each
        ratings = {p: 2300 - 12 * i for i, p in enumerate(ranked)}
        reach = {}
        odds = simulate_projected(ranked, ratings, False, 1500, 1, reach=reach)
        self.assertAlmostEqual(sum(odds.values()), 1.0, places=6)
        for k, n in (("qf", 8), ("sf", 4), ("f", 2)):
            self.assertAlmostEqual(sum(reach[k].values()), n, places=6)
        self.assertEqual(max(odds, key=odds.get), "S1")

    def test_position_grid_rows_are_probabilities(self):
        t = SoccerPipelineTests("test_competition_file_is_complete_and_consistent")
        t.setUp()
        g = t.payload()["positions"]
        self.assertEqual(len(g["teams"]), 6)
        for row in g["p"]:
            self.assertAlmostEqual(sum(row), 1.0, places=2)
        for k in range(6):  # every place is filled by exactly one team in each run
            self.assertAlmostEqual(sum(row[k] for row in g["p"]), 1.0, places=2)

    def test_sitemap_lists_every_page(self):
        from pipeline import build
        with tempfile.TemporaryDirectory() as tmp:
            n = build.write_sitemap([{"sport": "soccer", "id": "eng.1"}], {"Arsenal|soccer": "soccer-arsenal"}, site_dir=tmp)
            with open(os.path.join(tmp, "sitemap.xml")) as f:
                xml = f.read()
        self.assertEqual(n, 4)
        self.assertIn("competition.html?sport=soccer&amp;id=eng.1", xml)
        self.assertIn("team.html?id=soccer-arsenal", xml)


if __name__ == "__main__":
    unittest.main()
