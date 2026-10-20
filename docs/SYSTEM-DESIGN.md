# System Design

SportsPred is a static website backed by a scheduled Python job. The job pulls public results, rates every team and player, simulates what's left of each competition, and writes JSON. The website only reads that JSON, so there's no server and no database.

## Architecture

```mermaid
flowchart TD
  subgraph Sources["Public data (no keys)"]
    E1[ESPN soccer scoreboard<br/>results + fixtures by year]
    E2[ESPN soccer standings<br/>group tables]
    E3[ESPN tennis scoreboard<br/>draws + results by date]
    M[martj42 international results CSV]
  end
  subgraph Pipeline["pipeline/ (Python, runs hourly in GitHub Actions)"]
    D1[soccer_data.py] --> S1[soccer_model.py<br/>Elo + Poisson goals model]
    D2[tennis_data.py] --> T1[tennis_model.py<br/>Elo + draw simulation]
    S1 --> S2[soccer_sim.py<br/>tables, league phase, groups, knockouts]
    S2 --> B1[soccer_build.py]
    T1 --> B2[tennis_build.py]
    B1 --> B[build.py]
    B2 --> B
  end
  Cache[(data/<br/>cached history)] <--> D1
  Cache <--> D2
  E1 --> D1
  E2 --> D1
  M --> D1
  E3 --> D2
  B --> J[(site/data/*.json)]
  J --> W[Static site<br/>index · competition · how it works]
  W --> P[GitHub Pages]
  P --> M[Mac app<br/>AppKit window + WKWebView]
```

## Components

| Component | Job |
|---|---|
| `soccer_data.py` | Fetches a calendar year of matches per competition from ESPN and turns each event into a compact match record (teams, score, status, stage, neutral venue, shoot-out winner). Finished years are cached in `data/soccer/`. Also reads group tables and the international results archive. |
| `soccer_model.py` | `Elo`: sequential ratings with a goal-difference multiplier, a home advantage, faster updates for new teams, and snapshots at chosen dates. `GoalsModel`: expected goals for each side = exp(base ± slope × rating gap / 400); goals are Poisson. It gives win/draw/loss chances and the likeliest score. `fit_goals_model` fits base and slope by maximum likelihood. |
| `soccer_sim.py` | Vectorised Monte Carlo (numpy). `sim_table` plays out remaining fixtures with per-simulation rating noise. Ties on points go to goal difference and goals scored, or first to a mini-table of the games between the teams level on points where the league does that (`tiebreak: "h2h"` in config: La Liga, Serie A). Each format adds its own rules: leagues (top of the table), UEFA's 36-team league phase (then playoffs, round of 16, two-legged ties, one-off final), groups then knockout, and World Cup qualifying groups (`simulate_qualifying`: chance to top the group, qualify directly, or reach the playoff or next-round places). Knockout ties are solved exactly from goal-difference distributions, not sampled. Knockouts already under way are rebuilt from the real ties (aggregate scores, shoot-out winners). |
| `soccer_build.py` | Runs the club and international pipelines: fits home advantage by grid search, runs Elo once with snapshots, simulates each competition today plus once per past match day (odds over time), and assembles the JSON for each competition. |
| `tennis_data.py` | Queries ESPN every 3 days of the calendar, per tour, and keeps that tour's singles draw for each event. Events finished more than 2 weeks ago are frozen to `data/tennis/`, so later runs only fetch recent dates. A day is only marked as done once every event on it is frozen, so an event still in progress can't drop out of the cache. `fetch_rankings` reads the current top 8 for projected Finals fields. |
| `tennis_model.py` | Tennis Elo (K = 250 / (matches + 5)^0.4, Slams × 1.1). Each player has an overall rating plus one each for hard, clay and grass (updated only by matches on that surface). Predictions use (1 − w) × overall + w × surface; `fit_surface_weight` picks w by log loss over the last year. Also holds `surface_of` (tournament name → surface), best-of-five conversion, `as_of` (the draw as it stood on a given day) and `simulate_draw`. For the season finales: `rr_groups` (groups worked out from who plays whom, because ESPN doesn't name them), `as_of_rr`, and `simulate_finals` (round robin → semis → final, with an optional projected field and seeded group draw). Draw and finale simulations also count which pairs meet in the final (the likeliest final). |
| `tennis_build.py` | Picks the Grand Slams, 1000-level events and the ATP/WTA Finals from 30 days ago to 45 days ahead, then simulates each one today and per past match day. For a finale with no groups yet, it fetches the top 8 in the rankings as a projected field. |
| `live_log.py` | Keeps each day's published odds (the headline number: title, or qualifying chance) in a `live` list inside each competition's JSON, one entry per day, for the current season only. Each run merges the local copy with the copy on the live site, then adds today's entry. |
| `check.py` | Runs after the build and before publishing. It also compares with the live site: any competition still running there (live or upcoming, next match not past) that's missing from this build fails the run, so a failed fetch can't quietly drop a league. `search.json`, `today.json` and `model.json` must exist, and top-4 / relegation / top-8 / knockout chances must add up to their number of places. Every listed competition must have its file; chances must sit between 0 and 1; title chances must add up to 1 (to the number of groups for qualifying, and to groups × places for qualifying places); match chances must add up to 1. Any problem fails the run, so the site keeps its last good version. |
| `build.py` | Entry point. Runs each part in isolation, so a failing part keeps its previous output. Writes `index.json` (competition summaries) and `model.json` (parameters and accuracy). |
| `mac/` | The Mac app: an AppKit window with a `WKWebView` showing the live site. It adds native menus (Settings ⌘, opens the site's settings panel; Go ⌘1–3; Back, Forward, Reload, Zoom; Help → Send Feedback), follows the page title in the window subtitle, opens off-site links in the default browser, and refreshes when you return after 15 minutes. Offline, it shows the last copy of the page from WebKit's cache (the site's data loader falls back to cached data and shows an "offline" notice), and only shows the Try again page if nothing is cached. The web view's own storage keeps the site's settings between launches. |
| `site/sw.js`, `manifest.webmanifest` | Makes the site installable on a phone and readable offline: pages, scripts and data are network-first (always the latest when online) with the last copy as a fallback, marked so the page shows an "offline" notice. Not used inside the Mac app, which has its own cache. |
| `site/` | Plain HTML, CSS and JavaScript, no build step. Chart.js (from cdnjs) draws the odds-over-time chart. `app.js` holds the shared header, settings dialog (⌘,), feedback tab, colour-coded tags and number formatting. |

## Main flows

**Scheduled refresh.** GitHub Actions (hourly, on push, or by hand) restores `data/` from the cache, runs the tests, runs `python -m pipeline.build`, then uploads `site/` to GitHub Pages.

**A soccer prediction.**
1. Load every match from 2021 onwards for 13 competitions (the 7 predicted, plus 6 rating-only leagues so clubs from smaller leagues are rated through Europe).
2. Fit home advantage (grid of 40–100 Elo) and the goals model on matches since July 2022.
3. Run Elo over all finished matches, keeping each match's pre-match ratings and snapshots on every replay day.
4. For each competition, take its current season and simulate the remaining fixtures 10,000 times. The title chance is the share of simulations a team wins.
5. Replay: for each past match day, the same simulation (2,000 runs) uses only the results and ratings known that evening.

**World Cup qualifying.** Each confederation in `config.WC_QUALIFYING` is loaded alongside the international tournaments and stays hidden until it has fixtures in the next 300 days (none for 2030 as of Oct 2026). The groups come from ESPN standings, which describe the current stage. Only that stage's matches count: the latest stage played inside the groups, so earlier rounds don't leak into the tables. That stage's places (for example `"third": [2, 2, "Next round"]`) turn simulated finishing positions into chances. The chart follows chance to qualify for the 8 teams whose odds moved most.

**A tennis prediction.**
1. Rate every ATP or WTA singles match since 2024 in date order, tagging each with its tournament's surface, and update both the overall and the surface rating. Fit the surface blend w on the last 12 months.
2. For each covered event, rebuild the main draw. ESPN gives no bracket positions, so each known player is linked to the match they came from, and open (TBD) slots are filled at random from the unlinked winners of the round before.
3. Play the rest of the draw 10,000 times using each player's rating blended for that event's surface (best of five for men's Slams).
4. ATP/WTA Finals instead: groups come from the group-stage match graph (pieces of groups are joined at random while ESPN has only listed early matches). Every pair in a group of four meets once; standings go on wins, with a two-way tie decided by head-to-head. The semis pair each group winner with the other group's runner-up. Before any group is published, the projected top 8 is drawn into groups with seeds 1 and 2 kept apart and 3/4, 5/6 and 7/8 split. The table also shows the chance of reaching the semis.

## Where data lives

| Data | Location | Lifetime |
|---|---|---|
| Finished soccer years, finished tennis events | `data/` (committed seed, then the Actions cache) | Permanent |
| Current season / recent days | Refetched every run | – |
| Predictions | `site/data/*.json` (generated, git-ignored) | Rebuilt every run |
| Daily published odds (`live` in each competition file) | The published site; read back and extended every run | Current season or event |
| Viewer settings | Browser `localStorage` (`sportspred.settings`) | Per browser |

## Key decisions and trade-offs

- **Static site and a scheduled job, no server.** Free hosting, nothing to keep running, and the site loads instantly. The cost: predictions are only as fresh as the last run (usually under an hour old; GitHub sometimes delays scheduled runs by a few hours, and the site says when data is stale), not truly live in-match.
- **Free, keyless sources (ESPN public JSON, martj42).** No sign-ups or secrets. ESPN's feed is undocumented and could change; parsing is defensive, and a failing part keeps its previous output.
- **Elo + Poisson instead of a machine-learning model.** Few parameters, easy to explain on the How It Works page, and well calibrated (backtests are on that page). It ignores lineups, injuries and surface.
- **One club rating scale across leagues, with league strength learned from Europe.** Domestic games can't tell leagues apart, so after every European match between clubs from different leagues, every club in the winner's league moves up by 16 × (result − expected), and the loser's league moves down (`LEAGUE_SHIFT` in `soccer_build.py`). Backtest (Oct 2026), European matches: accuracy 54.0% → 56.9% and log loss 0.978 → 0.955 over the latest two seasons, and log loss 0.993 → 0.970 over the two before. All predicted matches: 0.987 → 0.981. Six extra leagues widen the European links. Cross-league gaps are still the least certain part of the model.
- **Rating noise in simulations (sd 50 Elo).** Without it, fixed ratings make long-range odds overconfident (Arsenal's 2026–27 pre-season chance went from 83% to 70% once it was added).
- **Odds over time by replay, not stored snapshots.** The chart is rebuilt each run from what was known on each day. It has full history from the first run and needs no stored state. If the model changes, the whole history is redrawn consistently.
- **Surface ratings blended with overall, by name lookup.** ESPN publishes no surface, so `config.TENNIS_SURFACES` maps tournament names to clay or grass, and everything else is hard. A separate surface rating alone is noisy (grass has few matches), so it is blended with the overall rating, and the data picks the mix. On the last year this lifted ATP from 63.7% to 63.9% called and WTA from 63.6% to 64.0%, with lower log loss on both. The blend is one parameter fitted and scored on the same year, so the gain is slightly optimistic.
- **Projected Finals field before the draw (user's choice).** Odds are available weeks earlier, at the cost of a stand-in field (52-week top 8 instead of the Race), clearly labelled on the page.
- **World Cup qualifying built ahead of time (user's choice).** It was built in October 2026 with no 2030 qualifiers scheduled, so it was checked by replaying the 2026 cycle with `SPORTSPRED_TODAY`. As of 1 Oct 2025, the model's favourite topped 11 of 12 European groups (the miss was Scotland, 19%). As of 1 Mar 2025, it gave Paraguay 83% to qualify from South America, which they did. Replays can't reproduce the past group lineup (ESPN standings only show the current stage), so a replay of an early date shows the latest stage's groups.
- **Chart colours follow the team.** The chart's 8 series are ordered by their first point (pre-season or pre-tournament odds), which doesn't change during the season, so a team keeps its colour as the race moves.
- **Accessible by default.** Checked with axe-core on every page in light and dark mode, with zero violations: white text sits only on fills that reach 4.5:1 (match bars use #256abf / #b8461a), text links use a darker blue than fills (`--link`) and are underlined inside running text, muted text is #6b6a65 in light mode, keyboard focus is outlined, and chart numbers are also available as tables.
- **One home page for "what's on".** `build.py` writes `today.json`: the next 36 hours of matches across every competition, with the model's pick, and the biggest moves (3+ points) between the last two days in each competition's published-odds log.
- **Honest track record.** Each competition page shows how often the model called it this season (and its Brier score). How It Works shows a calibration chart over the last 12 months: club soccer sits on the line, and tennis runs slightly hot at the extremes (ATP 94% calls won 88%).
- **Tried and not adopted (Oct 2026), so the model stays simpler:** separate scoring rates per league (Bundesliga 1.54 goals per team per game, Serie A and La Liga 1.23), which predicted goal counts slightly better (2.969 → 2.962) but results slightly worse (0.9818 → 0.9823); a shared-goals (bivariate Poisson) draw boost, which helped the earlier two seasons (0.980 → 0.978) but not the latest (0.981 either way); pulling club ratings toward the league average between seasons (log loss 0.990 → 0.991–0.999, worse at every strength); other club K-factors (K = 20 already gave the lowest log loss over 12 and 24 months); boosting or penalising tennis players back from a break (all variants worse; ESPN lacks Challenger and ITF results, so many apparent breaks aren't real); softening tennis probabilities (fitted on one year and tested on the next, it helped ATP 0.6337 → 0.6324 but hurt WTA 0.6277 → 0.6285).
- **Live odds stored on the published site, not in git.** Every run reads the previous `live` log from `SITE_URL` and republishes it with today's entry, so there are no bot commits or extra storage. Trade-off: if the site is deleted or unreachable for a whole day, that day is missing, and the log restarts if the site itself is lost. A failed deploy is harmless, because the next run reads the last good version. The chart shows the published dots next to the replay lines. The two differ when ratings settle after the fact or the model changes, which is what the comparison is for.
- **Mac app wraps the live site instead of bundling it.** It always shows the latest predictions without app updates, and the site and app can't drift apart. Trade-off: it needs an internet connection, and the app is only ad-hoc signed (not notarised), so other Macs need right-click → Open the first time.
- **Exact knockout-tie maths.** Tie probabilities come from convolving goal-difference distributions, so they're cached per pairing and the per-simulation loop stays cheap.
- **UEFA knockouts follow the real format.** `uefa_knockout` runs the 2024- structure. 9th–24th play off in seeded pools (9/10 v 23/24 … 15/16 v 17/18), each pool's winners meet the matching seeds (15–18 v 1/2 …), and the bracket is fixed from the round of 16 (1 and 2 only meet in the final). Real ties from ESPN override the simulated draw at every round, and part-played two-legged ties are finished from the real aggregate. Replaying 2025–26: 24 clubs with a chance after the league phase, 16 after the playoffs, then 8, 4, and PSG at 100% after the final.
- **Tennis open slots are approximated.** ESPN publishes no draw positions (see above).
- **A failed fetch never empties the cache, and never empties a competition.** A past year that fails to download is no longer cached as empty, which used to hide that year permanently. If a competition's latest data can't be fetched, its last good file (local or from the live site) is republished marked `stale` and shown as "Not refreshed", the rest of the site updates as normal, and its odds log isn't extended with a fake entry.
- **Title odds are graded, not just matches.** `title_backtest.py` rebuilds the odds for every finished season and tournament since the ratings' warm-up, as of the day before it started, and records the champion's chance and rank (summary in How It Works). Oct 2026: the pre-season favourite won 10 of 22 club seasons (champion in our top 3: 18), ATP favourites won 13 of 32 tournaments, WTA favourites 6 of 37 (women's tennis is less predictable). On average the champion was given 32% / 27% / 11%, against 5% / 4% / 3% if every entrant were equal.
- **Matches that matter.** In the league simulation, the next 15 games' simulated results are kept, so each contender's title chance can be split by that game's result (`match_swings`). Games are ranked by the biggest gap: for example, Barcelona v Real Madrid moves Barcelona between 88% (win) and 68% (loss). This costs no extra simulations.
- **What if, in the browser.** League files carry `whatif`: the table so far and every remaining fixture's expected goals. The page re-runs 2,000 seasons in JavaScript with the same rating noise, and any picked results are fixed (counted as 1–0 or 0–0), so it needs no server.
- **Team and player pages from what's already built.** `build.py` gathers each name's rows, upcoming and recent games from the competition files into `site/data/teams/<sport>-<name>.json`. Rating histories (pre-match ratings over the last year, plus today's) come from the builds through `data/histories/` (not published). `ratings.json` holds every current rating and the model constants for the How It Works compare tool, which uses the same formulas as the pipeline.
- **Explained predictions.** Each upcoming match carries both ratings, home advantage, expected goals and the last five meetings (club history since 2021, international since 1990, tennis since 2024). The page draws the score grid from the same Poisson model.
- **Projected tennis odds before the draw.** Grand Slams and 1000-level events with no players in the main draw yet use the top 64 in the rankings. Every simulation builds a fresh draw by the seeding rules (1 and 2 in opposite halves, 3–4 in the other quarters, 5–8 one per quarter, 9–16 one per eighth) and plays it out (`seeded_draw`, `simulate_projected`). This ignores byes, qualifiers and withdrawals, and is labelled "projected" until ESPN lists the real draw.
- **How far, not just who wins.** Tennis draws also report the chance of reaching the quarter-finals, semi-finals and final, and leagues report the full finishing-position grid (each team × each place). Both come from the same simulations at no extra cost.
- **One judge for results.** `SP.verdict` (in `app.js`) decides "Called it", "Missed" or "Upset" (we gave the result under 25%) for every page, so the competition and team pages can't disagree.
- **Discoverable.** Each build writes `site/sitemap.xml` (home, How It Works, every competition and team page). A `robots.txt` would only be read at the domain root, which a GitHub project page doesn't control, so the sitemap is for submitting to search tools.
- **Settled races by arithmetic, not simulation.** `certainties` (in `soccer_build.py`) marks a league title, top-places finish or relegation as certain or impossible when no combination of remaining results can change it: each team's worst case is losing every game left and its best case winning them all. Games between rivals are ignored, so a race can be called a little later than in reality but never earlier. Tables show "Sure" / "Out" (and "Safe" / "Down") instead of a percentage, and tests check these always agree with the simulations (0% or 100%).
- **Points against expectation.** Each finished league game is worth 3 × P(win) + P(draw) expected points from its pre-match chances; the table shows points won minus that. Oct 2026: Barcelona +6.0, Valencia −6.2. Gaps like these usually shrink, which is one reason the ratings (not the table) drive the odds.
- **Run-in difficulty.** For each team's remaining fixtures, the points a team of the league's average rating would expect from them (home advantage included), and the average opponent rating. Lower is harder; it is a description only (the simulations already play the real fixtures).
- **Head-to-head tie-breakers where they come first.** La Liga and Serie A split teams level on points by the games between them (points, then goal difference) before overall goal difference. The simulation keeps a points and goal-difference matrix between every pair in each run (`int16`, about 8 MB each for 10,000 runs of 20 teams) and sorts with `np.lexsort`. Serie A's playoff for a tie on top or in the last relegation place isn't modelled, and the in-browser What if tool still uses goal difference.
- **Accuracy by competition against a no-skill baseline.** `model.json` holds `by_competition`: each league, Europe, internationals, and ATP/WTA by level (Grand Slams, the 1000s and Finals we predict, other tour events), over the last 12 months. The soccer baseline knows only how often home wins, draws and away wins happen in that competition; tennis's is a coin toss. Skill = 1 − our log loss / baseline log loss. Oct 2026: Premier League 4.4% (the hardest league to call), Serie A 9.0%, internationals 15.8%, WTA Grand Slams 15.8%, other ATP events 6.4%.
- **Likeliest final.** Tennis draws and the Finals count each pair that contests the final across the same simulations (Paris 2026, projected: Sinner v Alcaraz 16%).
- **Small conveniences that need no new data.** Followed teams on the home page show their next game (read from their team page file); search also finds competitions; team pages rank the rating among every club we rate (or, for players, among the tour's top 300, overall and on each court); `?` opens a keyboard shortcuts panel on every page (also Help → Keyboard Shortcuts in the Mac app), and `/` jumps to search from any page.
- **Upsets.** A result the model gave under 25% is labelled an upset. The home page lists the week's biggest (Oct 2026: Venezia 1–0 Napoli, given 14%).
- **Security.** Every page sends a Content Security Policy: scripts only from the site and cdnjs, no inline script (the two inline scripts moved to `how.js` and `notfound.js`), `object-src 'none'`, `form-action 'none'`. Text from ESPN (team, player, round and competition names) is HTML-escaped wherever it reaches the page, including attributes.
- **Cache-busting on deploy.** `pipeline/stamp.py` (a CI step before upload) adds a content hash to every CSS/JS link (`app.js?v=…`). GitHub Pages lets browsers keep files for 10 minutes, so without this a visitor could get a new page script with an old shared script, which happened in testing.

## Testing

- Accessibility: axe-core 4.10 run against index, a soccer and a tennis competition page, How It Works and 404, in light and dark mode: no violations (Oct 2026).

- Mac app: built with `mac/build-app.sh` (universal binary, signature verified) and checked by hand: the live site loads, Settings… (⌘,) opens the settings panel, the Go menu navigates, and the subtitle follows the page.

- `tests/test_integration.py` also checks the seeding rules on 100 random draws, that projected odds and round-reach chances add up (8 quarter-finalists, 4 semi-finalists, 2 finalists), that every row and every place in the position grid sums to 1, and the sitemap.
- `pipeline/smoke.py` (CI, before publishing): every local link in every page resolves, every listed competition and team page has its file, and every script parses (`node --check`).
- `tests/test_integration.py` also checks the head-to-head tie-break (the same table sorts differently under goal difference and head-to-head), that settled races are only claimed when arithmetic allows and agree with the simulated odds, that run-in and expected points add up, the no-skill baseline, and that the likeliest finals' chances sum to 1.
- `tests/test_integration.py` (18 tests, synthetic data, no network): builds a whole competition file and passes it through the publish check (and makes sure a broken one fails); keeps the last good copy when a fetch fails without logging a fake day; checks that a lost real playoff tie can never be won and that a fully played real knockout (with a draw that differs from the model's bracket) always gives the real champion; builds a tennis event file from a part-played draw; grades title odds; and cache-busts asset links.
- `tests/test_models.py` (31 unit tests, no network): probabilities sum to one and follow rating gaps, Elo is zero-sum and snapshots are taken in the right order, the goals-model fit recovers known parameters, tie maths is symmetric and respects aggregate leads, knockout state reads aggregates and shoot-outs, best-of-five helps favourites, draw simulation handles TBD slots, `as_of` undoes later results, the surface lookup works, surface ratings only move on their own surface, the blend fit prefers surface ratings when results really do split by surface, and finales get their groups from the match graph, settle two-way ties by head-to-head, return title odds summing to 1 and semi odds summing to 4, keep the top two seeds apart in projected draws, and `as_of_rr` hides semi-final players until the groups are done, the live log keeps the latest entry per day and drops other seasons, and it logs the right headline number per format.
- Backtest on every build: each match in the last 12 months is scored against its pre-match prediction (accuracy, Brier score, log loss, predicted vs actual draw rate). Results are in `model.json` and on the How It Works page. Tennis also reports `backtest_overall_only`, so the surface gain stays visible.
- CI runs the tests before every build and `pipeline.check` after it; a failure in either blocks publishing.
- Unit tests also cover the publish check (good, unbalanced and empty files, plus qualifying sums) and the calibration bands and track record.

## Known limits

- No injuries, suspensions, transfers or lineups.
- Tennis surfaces come from a name list; unlisted events count as hard, and indoor and outdoor hard courts are treated alike.
- Points deductions aren't modelled. Head-to-head tie-breakers are (La Liga, Serie A), but not Serie A's playoff for a tie on top or in the last relegation place, nor head-to-head rules further down other leagues' lists; What if uses goal difference.
- Before ESPN lists a UEFA round, its pairings within each seeded pool are drawn at random (as UEFA does); tennis open slots aren't placed in the exact half of the draw.
- Flags come from a fixed mapping of ESPN country codes and national-team names; anything not listed shows no flag.
- ATP/WTA Finals: three-way ties are split at random (not by sets/games). Before the draw, the field comes from the 52-week rankings (ESPN has no Race), so withdrawals and alternates only appear once the real draw does.
- The Next Gen ATP Finals aren't predicted.
- World Cup qualifying uses the 2026 cycle's places until 2030's are confirmed; "best runners-up" rules are simplified to every runner-up; Oceania (knockout only) isn't covered; inter-confederation playoffs aren't simulated.
- Tennis events only get odds once ESPN publishes the main draw.
- Independent Poisson goals slightly under-predict draws (about 22.7% predicted vs 24.1% actual for clubs).
