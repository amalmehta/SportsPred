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

## Look at the site locally

```bash
python3 -m http.server 8765 --directory site
```

Then open http://localhost:8765. Opening the HTML files straight from disk won't work, because the pages load their data with `fetch`.

## Run the tests

```bash
python3 -m unittest discover -s tests
```

## Using the site

- **Home page:** one card per competition with the current favourite and their chance to win. Use the chips to show only soccer or only tennis.
- **Competition page:** the favourite, a chart of title odds over the season or tournament (hover for exact values), every team's or player's chances, upcoming matches with win/draw/loss chances, and recent results marked "Called it" or "Missed".
- **Settings:** the gear button, or ⌘, (Ctrl+, on Windows and Linux). Choose appearance, percent or decimal odds, local time or UTC, what the home page shows first, and whether finished events are listed. Settings are saved in your browser.
- **Feedback:** the small tab on the right edge opens a pre-filled GitHub issue.

## Hosting (GitHub Pages)

`.github/workflows/update.yml` runs every 3 hours, on every push to `main`, and when started by hand from the Actions tab. It runs the tests, rebuilds the predictions and publishes `site/` to GitHub Pages. The downloaded history is kept in the Actions cache between runs. One-time setup: in the repository settings, set **Pages → Source** to **GitHub Actions**.

## Changing what's covered

Edit `pipeline/config.py`:

- `SOCCER_COMPETITIONS`: club competitions (any ESPN soccer league slug, e.g. `ned.1`).
- `INTERNATIONAL_COMPETITIONS`: international tournaments, shown only while they have fixtures.
- `TENNIS_TOURS`: name keywords for the tennis events that get predictions.
- `TENNIS_SURFACES`: name keywords for clay and grass events (everything else counts as hard court).
- `SIMS_TODAY` / `SIMS_REPLAY`: simulation counts (more runs are steadier but slower).

To test a past date, set `SPORTSPRED_TODAY=YYYY-MM-DD` before running the build.
