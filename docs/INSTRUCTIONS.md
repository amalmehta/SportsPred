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
| ⌥⌘O | Open the page in your browser |
| File → Share… | Share the page (Messages, Mail, AirDrop…) |
| Help → Send Feedback… | Opens the feedback panel |

Links that leave the site, such as the GitHub feedback form, open in your default browser. Without an internet connection, the app shows a "Can't reach SportsPred" page with a Try again button. To point the app somewhere else (for a fork), change `SPSiteURL` in `mac/Info.plist`.

## Run the tests

```bash
python3 -m unittest discover -s tests
```

## Using the site

- **Home page:** one card per competition with the current favourite and their chance to win. Use the chips to show only soccer or only tennis, or type in **Find a team or player** to see every competition someone is in and their chances.
- **Competition page:** the favourite, a chart of title odds over the season or tournament (hover for exact values, or **Show as table** for every day's numbers), the season's track record, every team's or player's chances, upcoming matches with win/draw/loss chances, and recent results marked "Called it" or "Missed".
- **Settings:** the gear button, or ⌘, (Ctrl+, on Windows and Linux). Choose appearance, percent or decimal odds, local time or UTC, what the home page shows first, and whether finished events are listed. Settings are saved in your browser.
- **Feedback:** the small tab on the right edge (a button in the corner on phones) opens a pre-filled GitHub issue.
- **Home page extras:** "Coming up in the next day or so" lists every match across competitions with the model's pick, and "Biggest moves since yesterday" shows whose odds changed most.
- **Share:** each competition page has a Share button (the share sheet on phones and Safari, otherwise it copies the link). Shared links show a preview card.
- **On your phone:** open the site in Safari or Chrome and choose **Add to Home Screen**. It opens like an app and shows the last predictions when you're offline.

## Hosting (GitHub Pages)

`.github/workflows/update.yml` runs hourly (GitHub sometimes delays scheduled runs), on every push to `main`, and when started by hand from the Actions tab. It runs the tests, rebuilds the predictions and publishes `site/` to GitHub Pages. The downloaded history is kept in the Actions cache between runs. One-time setup: in the repository settings, set **Pages → Source** to **GitHub Actions**.

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
