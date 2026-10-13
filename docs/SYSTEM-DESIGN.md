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
  subgraph Pipeline["pipeline/ (Python, runs every 3 hours in GitHub Actions)"]
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
```

## Components

| Component | Job |
|---|---|
| `soccer_data.py` | Fetches a calendar year of matches per competition from ESPN and turns each event into a compact match record (teams, score, status, stage, neutral venue, shoot-out winner). Finished years are cached in `data/soccer/`. Also reads group tables and the international results archive. |
| `soccer_model.py` | `Elo`: sequential ratings with a goal-difference multiplier, a home advantage, faster updates for new teams, and snapshots at chosen dates. `GoalsModel`: expected goals for each side = exp(base ± slope × rating gap / 400); goals are Poisson. It gives win/draw/loss chances and the likeliest score. `fit_goals_model` fits base and slope by maximum likelihood. |
| `soccer_sim.py` | Vectorised Monte Carlo (numpy). `sim_table` plays out remaining fixtures with per-simulation rating noise. Each format adds its own rules: leagues (top of the table), UEFA's 36-team league phase (then playoffs, round of 16, two-legged ties, one-off final), and groups then knockout. Knockout ties are solved exactly from goal-difference distributions, not sampled. Knockouts already under way are rebuilt from the real ties (aggregate scores, shoot-out winners). |
| `soccer_build.py` | Runs the club and international pipelines: fits home advantage by grid search, runs Elo once with snapshots, simulates each competition today plus once per past match day (odds over time), and assembles the JSON for each competition. |
| `tennis_data.py` | Queries ESPN every 3 days of the calendar, per tour, and keeps that tour's singles draw for each event. Events finished more than 2 weeks ago are frozen to `data/tennis/`, so later runs only fetch recent dates. |
| `tennis_model.py` | Tennis Elo (K = 250 / (matches + 5)^0.4, Slams × 1.1). Each player has an overall rating plus one each for hard, clay and grass (updated only by matches on that surface). Predictions use (1 − w) × overall + w × surface; `fit_surface_weight` picks w by log loss over the last year. Also holds `surface_of` (tournament name → surface), best-of-five conversion, `as_of` (the draw as it stood on a given day) and `simulate_draw`. |
| `tennis_build.py` | Picks the Grand Slams and 1000-level events from 30 days ago to 45 days ahead, then simulates each one today and per past match day. |
| `build.py` | Entry point. Runs each part in isolation, so a failing part keeps its previous output. Writes `index.json` (competition summaries) and `model.json` (parameters and accuracy). |
| `site/` | Plain HTML, CSS and JavaScript, no build step. Chart.js (from cdnjs) draws the odds-over-time chart. `app.js` holds the shared header, settings dialog (⌘,), feedback tab, colour-coded tags and number formatting. |

## Main flows

**Daily refresh.** GitHub Actions (every 3 hours, on push, or by hand) restores `data/` from the cache, runs the tests, runs `python -m pipeline.build`, then uploads `site/` to GitHub Pages.

**A soccer prediction.**
1. Load every match from 2021 onwards for 13 competitions (the 7 predicted, plus 6 rating-only leagues so clubs from smaller leagues are rated through Europe).
2. Fit home advantage (grid of 40–100 Elo) and the goals model on matches since July 2022.
3. Run Elo over all finished matches, keeping each match's pre-match ratings and snapshots on every replay day.
4. For each competition, take its current season and simulate the remaining fixtures 10,000 times. The title chance is the share of simulations a team wins.
5. Replay: for each past match day, the same simulation (2,000 runs) uses only the results and ratings known that evening.

**A tennis prediction.**
1. Rate every ATP or WTA singles match since 2024 in date order, tagging each with its tournament's surface, and update both the overall and the surface rating. Fit the surface blend w on the last 12 months.
2. For each covered event, rebuild the main draw. ESPN gives no bracket positions, so each known player is linked to the match they came from, and open (TBD) slots are filled at random from the unlinked winners of the round before.
3. Play the rest of the draw 10,000 times using each player's rating blended for that event's surface (best of five for men's Slams).

## Where data lives

| Data | Location | Lifetime |
|---|---|---|
| Finished soccer years, finished tennis events | `data/` (committed seed, then the Actions cache) | Permanent |
| Current season / recent days | Refetched every run | – |
| Predictions | `site/data/*.json` (generated, git-ignored) | Rebuilt every run |
| Viewer settings | Browser `localStorage` (`sportspred.settings`) | Per browser |

## Key decisions and trade-offs

- **Static site and a scheduled job, no server.** Free hosting, nothing to keep running, and the site loads instantly. The cost: predictions are only as fresh as the last run (up to 3 hours old), not truly live in-match.
- **Free, keyless sources (ESPN public JSON, martj42).** No sign-ups or secrets. ESPN's feed is undocumented and could change; parsing is defensive, and a failing part keeps its previous output.
- **Elo + Poisson instead of a machine-learning model.** Few parameters, easy to explain on the How It Works page, and well calibrated (backtests are on that page). It ignores lineups, injuries and surface.
- **One club rating scale across leagues.** European matches link the leagues; six extra leagues improve coverage of European opponents. Cross-league gaps are still the least certain part of the model.
- **Rating noise in simulations (sd 50 Elo).** Without it, fixed ratings make long-range odds overconfident (Arsenal's 2026–27 pre-season chance went from 83% to 70% once it was added).
- **Odds over time by replay, not stored snapshots.** The chart is rebuilt each run from what was known on each day. It has full history from the first run and needs no stored state. If the model changes, the whole history is redrawn consistently.
- **Surface ratings blended with overall, by name lookup.** ESPN publishes no surface, so `config.TENNIS_SURFACES` maps tournament names to clay or grass, and everything else is hard. A separate surface rating alone is noisy (grass has few matches), so it is blended with the overall rating, and the data picks the mix. On the last year this lifted ATP from 63.7% to 63.9% called and WTA from 63.6% to 64.0%, with lower log loss on both. The blend is one parameter fitted and scored on the same year, so the gain is slightly optimistic.
- **Exact knockout-tie maths.** Tie probabilities come from convolving goal-difference distributions, so they're cached per pairing and the per-simulation loop stays cheap.
- **Approximate brackets.** The UEFA draw (seeded pairs) and tennis open slots are approximated, as described above.

## Testing

- `tests/test_models.py` (18 unit tests, no network): probabilities sum to one and follow rating gaps, Elo is zero-sum and snapshots are taken in the right order, the goals-model fit recovers known parameters, tie maths is symmetric and respects aggregate leads, knockout state reads aggregates and shoot-outs, best-of-five helps favourites, draw simulation handles TBD slots, `as_of` undoes later results, the surface lookup works, surface ratings only move on their own surface, and the blend fit prefers surface ratings when results really do split by surface.
- Backtest on every build: each match in the last 12 months is scored against its pre-match prediction (accuracy, Brier score, log loss, predicted vs actual draw rate). Results are in `model.json` and on the How It Works page. Tennis also reports `backtest_overall_only`, so the surface gain stays visible.
- CI runs the tests before every build, and a failing test blocks publishing.

## Known limits

- No injuries, suspensions, transfers or lineups.
- Tennis surfaces come from a name list; unlisted events count as hard, and indoor and outdoor hard courts are treated alike.
- Points deductions and head-to-head tie-breakers aren't modelled.
- The UEFA knockout draw is approximated by seeding; tennis open slots aren't placed in the exact half of the draw.
- Round-robin events (ATP and WTA Finals) aren't predicted.
- Tennis events only get odds once ESPN publishes the main draw.
- Independent Poisson goals slightly under-predict draws (about 22.7% predicted vs 24.1% actual for clubs).
