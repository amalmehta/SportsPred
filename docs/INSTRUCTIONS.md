# Instructions

## What you need

- Python 3.8 or newer
- `numpy` (`pip install -r requirements.txt`)
- An internet connection. Every data source is free and needs no key.

## Build the predictions

From the project folder:

```bash
python3 -m pipeline.build
```

This downloads results and fixtures, rates every team and player, runs the simulations and writes the website's data to `site/data/`. The first run downloads a few years of history (about 5 minutes). Later runs reuse the cached history in `data/` and take about a minute.

To rebuild only one part:

```bash
python3 -m pipeline.build --only tennis
```

`--only` accepts `clubs`, `international` or `tennis`, and can be repeated.

Then check the output the way CI does before publishing:

```bash
python3 -m pipeline.check
```

## Look at the site locally

```bash
python3 -m http.server 8765 --directory site
```

Then open http://localhost:8765. Opening the HTML files straight from disk won't work, because the pages load their data with `fetch`.

## Mac app

A native Mac window around the live site, with Mac menus and shortcuts. It needs Xcode (or the Xcode command-line tools) and macOS 12 or newer.

```bash
./mac/build-app.sh
```

This builds `mac/build/SportsPred.app`, a universal app for Apple silicon and Intel. Open it, or drag it to Applications. Add `--zip` to also make `mac/build/SportsPred.zip` to share. The app is signed for this Mac only and isn't notarised, so on another Mac, right-click it and choose **Open** the first time.

| Shortcut | Does |
|---|---|
| ⌘, | Settings (the site's settings panel) |
| ⌘1 / ⌘2 / ⌘3 | Soccer / Tennis / How It Works |
| ⇧⌘H | Home |
| ⌘[ / ⌘] | Back / Forward (or swipe) |
| ⌘R | Reload (it also refreshes on its own when you come back after 15 minutes) |
| ⌘+ / ⌘− / ⌘0 | Zoom in / out / actual size |
| ⇧⌘C | Copy a link to the page you're on |
| (on launch) | Reopens the page you were last on |
| ⌥⌘O | Open the page in your browser |
| ⌘F | Find a team or player |
| ⌥⌘1 – ⌥⌘9 | Your Teams menu: the teams and players you follow (★ on the site); also in the Dock menu |
| File → Share… | Share the page (Messages, Mail, AirDrop…) |
| Help → Send Feedback… | Opens the feedback panel |
| Help → Keyboard Shortcuts | Every shortcut (or press ? on any page) |

Links that leave the site, such as the GitHub feedback form, open in your default browser. Without an internet connection, the app shows a "Can't reach SportsPred" page with a Try again button. To point the app somewhere else (for a fork), change `SPSiteURL` in `mac/Info.plist`.

## Run the tests

```bash
python3 -m unittest discover -s tests
```

## Using the site

- **Home page:** one card per competition with the current favourite and their chance to win, and the runner-up beneath. Use the chips to show only soccer or only tennis, or type in **Find a team or player** to see every competition someone is in and their chances.
- **Competition page:** the favourite, a chart of title odds over the season or tournament (hover for exact values, or **Show as table** for every day's numbers), the season's track record, every team's or player's chances, upcoming matches with win/draw/loss chances, and recent results marked "Called it" or "Missed".
- **Settings:** the gear button, or ⌘, (Ctrl+, on Windows and Linux). Choose appearance, percent or decimal odds, local time or UTC, what the home page shows first, and whether finished events are listed. Settings are saved in your browser.
- **Feedback:** the small tab on the right edge (a button in the corner on phones) opens a pre-filled GitHub issue.
- **Settled races:** once arithmetic alone decides a race, league tables say **Sure** or **Out** (and **Safe** or **Down** for relegation) instead of a percentage, with a badge such as "Title won" next to the team.
- **Points vs expected** (league tables, wider screens): points won minus what each game's pre-match chances were worth. Plus means a team is ahead of its results so far. A line under the table names who's most ahead and behind.
- **Run-in:** league pages list who has the hardest games left, measured by the points an average side would expect from those fixtures.
- **How far in Europe:** Champions and Europa League tables show each club's chance of reaching the last 16, quarter-finals, semi-finals and final. International tournaments show the chance of getting out of the group.
- **Matches that matter at the bottom:** league pages also show the games that swing the relegation fight most.
- **Points needed:** league pages show roughly how many points the title, the top places and safety will take, and the table shows each team's likely finishing range.
- **Season so far:** a folded section on soccer pages lists the season's biggest upsets and whose rating has risen or fallen most in the last 30 days. Recent results show **Exact score** when the likeliest score came up.
- **Save image:** under the odds chart, saves it as a PNG with a title and legend.
- **Waiting on an opponent:** tennis pages list matches where one player is through and the other isn't known yet, with each possible opponent's chance.
- **Feed:** subscribe to `feed.xml` (linked in the footer) in a feed reader for the week's upsets, the day's biggest odds moves and new champions.
- **Likeliest final:** tennis pages show the likeliest pairings for the final under the favourite.
- **Odds tables:** **Download CSV** saves any competition's table. Tennis tables show the chance of reaching the quarter-finals, semi-finals and final; leagues have **Every finishing position**, a grid of how likely each team is to end up in each place. Before a big tennis event's draw is out, its odds are projected from the rankings.
- **Team and player pages:** click any name in a table, in search or under Your teams to see where their rating ranks, settled races, points against expectation and how hard their run-in is (for players, overall and on each court), their form (last five results), next match with their chances, chances everywhere, their rating over the last year (and, for tennis players, by court), and their next and recent games.
- **Why these numbers?** Under each upcoming match: both ratings, home advantage, expected goals, a grid of likely scores and the last meetings.
- **Matches that matter / What if…?** League pages show the games that swing the title race most, and let you pick results for the next games and replay the season in your browser.
- **How accurate is it?** How It Works shows accuracy over the last year, competition by competition, against a baseline with no skill, plus a calibration chart and how often the favourites won.
- **Compare any two:** on How It Works, pick two clubs, national teams or players to see the model's chances and likely scores.
- **Follow teams:** tap ☆ next to any team or player in a competition's table (or in search results). They appear under **Your teams** at the top of the home page, with their next game and their chances everywhere. Saved in this browser.
- **Add to calendar:** on a competition page, **Add to calendar** downloads its upcoming matches, with the model's chances in each event, as an `.ics` file for Calendar, Outlook or Google Calendar.
- **Chart legend:** click a team in the legend to hide or show its line.
- **Search shortcuts:** press / to jump to search (from any page), use ↑ ↓ to move through results, Enter to open, Esc to clear. Search finds competitions as well as teams and players.
- **Keyboard shortcuts:** press ? on any page to see them all.
- **Home page extras:** "Coming up in the next day or so" lists every match across competitions with the model's pick, and "Biggest moves since yesterday" shows whose odds changed most.
- **Share:** each competition page has a Share button (the share sheet on phones and Safari, otherwise it copies the link). Shared links show a preview card.
- **On your phone:** open the site in Safari or Chrome and choose **Add to Home Screen**. It opens like an app and shows the last predictions when you're offline.

## Use the data

Every number on the site comes from JSON files you can read yourself, from a script or from another web page: GitHub Pages allows cross-site requests (`Access-Control-Allow-Origin: *`). They are rebuilt about hourly and browsers may cache them for 10 minutes. The base address is `https://amalmehta.github.io/SportsPred/`.

| File | What's in it |
|---|---|
| `data/index.json` | Every competition: id, sport, name, status, favourite and runner-up with their chances, next match |
| `data/soccer/<id>.json`, `data/tennis/<id>.json` | One competition: `table` (every team or player with chances, points, rating, settled races, likely finish), `upcoming` (match chances, expected goals, likely score), `recent` (results with the pre-match chances), `history` (odds over time), `live` (odds as published each day), `lines` (points needed), `run_in`, `swings`, `positions` |
| `data/teams/<sport>-<name>.json` | One team or player: chances everywhere, rating history, next and recent games (`data/teams.json` maps names to these files) |
| `data/today.json` | The next day and a half of matches everywhere, big games, upsets and odds moves |
| `data/ratings.json` | Every current rating, with the constants needed to turn two ratings into match chances |
| `data/model.json` | Fitted parameters and accuracy (overall, by competition, calibration, title-odds record) |
| `feed.xml` | Atom feed of upsets, big moves and champions |

Chances are probabilities between 0 and 1. Dates are UTC (`2026-10-21T19:00Z`). Field names can change as the site grows; nothing here is a stable API.

```bash
curl -s https://amalmehta.github.io/SportsPred/data/index.json
```

## Hosting (GitHub Pages)

`.github/workflows/update.yml` runs hourly (GitHub sometimes delays scheduled runs), on every push to `main`, and when started by hand from the Actions tab. It runs the tests, rebuilds the predictions, checks them (`pipeline.check`), smoke-tests the built site (`pipeline.smoke`), adds content hashes to the CSS/JS links (`pipeline.stamp`) and publishes `site/` to GitHub Pages. If one competition's data can't be fetched, that competition keeps its last good predictions (marked "Not refreshed") and everything else still updates. The downloaded history is kept in the Actions cache between runs. One-time setup: in the repository settings, set **Pages → Source** to **GitHub Actions**.

## Changing what's covered

Edit `pipeline/config.py`:

- `SOCCER_COMPETITIONS`: club competitions (any ESPN soccer league slug, e.g. `ned.1`).
- `INTERNATIONAL_COMPETITIONS`: international tournaments, shown only while they have fixtures.
- `WC_QUALIFYING`: World Cup qualifying per confederation, with the qualifying and playoff places per group for each stage. Update the places once FIFA confirms the 2030 allocation.
- `TENNIS_TOURS`: name keywords for the tennis events that get predictions.
- `TENNIS_SURFACES`: name keywords for clay and grass events (everything else counts as hard court).
- `TENNIS_FINALS` / `TENNIS_EXCLUDE`: which events use the round-robin finale format, and names to skip (the Next Gen ATP Finals).
- `SITE_URL`: where the site is published; each run reads the earlier daily-odds log from there (change it if you fork the project).
- `SIMS_TODAY` / `SIMS_REPLAY`: simulation counts (more runs are steadier but slower).

To test a past date, set `SPORTSPRED_TODAY=YYYY-MM-DD` before running the build.
