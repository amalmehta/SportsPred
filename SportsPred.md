PROJECT NAME: SportsPred

META-INSTRUCTIONS:

<Read it all before acting. Ask about anything unclear, contradictory or
 underspecified — before starting and mid-build. Ask in the question widget
 (AskUserQuestion): related questions batched, concrete options, your
 recommendation first. Plain text only if the widget isn't available.>

<Don't expand scope. Anything not listed here is a proposal, including changes
 to this file — propose it, don't do it.>

<Prefer doing over describing: run the code, write the files, test it.>

<Always in scope, no proposal needed: when it goes on GitHub, a README that is
 easy to read at a glance — a line on what it is, then clear visuals
 (screenshots, a diagram or a chart), then links. Everything else goes in
 linked files: docs/INSTRUCTIONS.md (setup, run, use),
 docs/SYSTEM-DESIGN.md (see below) and docs/FILE-STRUCTURE.md (what's where). If what you're
 building is an application rather than a script, also a small unobtrusive feedback tab, and a settings
 button or tab (⌘, on the Mac) that gathers its preferences in one place.>

<If what you're building is an application, build it as a Mac app first; the
 website comes after, as its own step.>

<When an application takes files as input, offer a visible Upload button that
 opens the file picker, accept files dragged anywhere onto the window (not
 only onto a small drop zone), and accept pasting them with ⌘V.>

<Color-code tags, categories and types by similarity: related ones share a
 hue family, with shades far enough apart to tell them apart at a glance, in
 both light and dark mode.>

<Name things the way a person would say them — "Goal Tracker", not
 goal_tracker — for the app, its windows, titles, files people open, repo
 descriptions and README headings. When you create the GitHub repo, name it
 with no "_" or "-": one word or joined words, e.g. GoalTracker.>

<Always in scope: a system design doc in the codebase, docs/SYSTEM-DESIGN.md,
 kept current as the build changes. Cover the architecture (with a Mermaid
 diagram), each component's job, the main flows, where data lives, the key
 design decisions and their trade-offs, how it's tested, and known limits.>

<Finish by listing every deliverable: path, what it is, how to check it works.>

<Git rules (no Claude attribution, never commit .claude/) are in
 ~/.claude/CLAUDE.md and apply on their own — nothing to repeat here.>

<Keep the changelog at the bottom current.>

CONTEXT:

Project type: Course / learning (material that teaches, with lessons and practice).

for selected sports / tournaments (do it live for every upcoming tourney), predict the winner. of course use past historical results based on the previous years/tournmanets accordingly. ask me if you aren’t sure. start with soccer and tennis.

DELIVERABLES:

website with sports predictions

OPEN QUESTIONS / ASSUMPTIONS:

Asked and answered (2026-10-13):
- Website first (the DELIVERABLES field overrides "Mac app first"); the Mac app wrapper was added afterwards on request.
- Predictions site plus one "How it works" page, no lessons or exercises.
- Free, keyless data: ESPN public scoreboard JSON (soccer + tennis), martj42 international results.
- Coverage: big five leagues, Champions League, Europa League, international tournaments while on;
  ATP/WTA Grand Slams and 1000s. Hosted on GitHub Pages in a new public repo, SportsPred.
- "Live": upcoming match predictions plus title odds over time (user, mid-build).

Decided without asking:
- Rebuilds every 3 hours (not once a day) so it stays "live"; in-match live odds are out of scope.
- Freshness (asked 2026-10-18): GitHub runs the hourly schedule only every ~4–5 hours on this repo. User chose to keep it as is rather than self-re-triggering runs; the site shows a notice when data is over 6 hours old.
- Odds over time are rebuilt each run by replaying the season with only what was known each day,
  so charts have full history from day one.
- Jeff Sackmann's tennis CSVs are gone (404), so tennis history comes from ESPN too, from 2024.
- Ratings: Elo. Soccer match chances from a Poisson goals model; 10,000 Monte Carlo runs.
- Six extra leagues (POR, NED, SCO, BEL, TUR, Conference League) feed ratings only.
- Not predicted: Next Gen ATP Finals, Europa Conference League, Oceania qualifying, intercontinental playoffs.
- World Cup qualifying (user chose to build now): dormant until 2030 qualifiers are scheduled; shows qualify / playoff / top-group chances; places follow the 2026 cycle until FIFA confirms 2030's.
- ATP/WTA Finals before the draw: field projected from the current top 8 in the rankings (user chose this; ESPN has no Race standings).
- No file input in this app, so no Upload button.
- Repo is public (needed for GitHub Pages on a free plan).

Proposals (not built):

CHANGELOG:

- 2026-10-13 — created
- 2026-09-15 — added meta-instruction: built-out applications include a small feedback tab
- 2026-09-15 — added meta-instruction: no "Claude" attribution in commits, PRs, or branches
- 2026-09-16 — added meta-instruction: always include a README when adding to GitHub
- 2026-09-16 — changed meta-instruction: ask clarifying questions in the question widget
- 2026-09-17 — added meta-instructions: Claude never a contributor; never commit .claude/
- 2026-09-26 — compressed the meta-instructions and every field prompt; git rules moved to the global instruction file
- 2026-09-27 — added meta-instruction: applications are built as a Mac app first, then a website
- 2026-09-28 — folded inputs, instructions, constraints, deliverables and done criteria into one free-form CONTEXT
- 2026-09-28 — changed meta-instruction: a README on GitHub always includes a visual
- 2026-09-28 — added meta-instruction: name things like a person would, never snake_case
- 2026-09-28 — changed meta-instruction: README leads with visuals; instructions live in a linked guide
- 2026-09-28 — changed meta-instruction: README is visuals and links; details in docs/INSTRUCTIONS.md and docs/FILE-STRUCTURE.md
- 2026-09-29 — changed meta-instruction: GitHub repo names have no "_" or "-"
- 2026-10-02 — added a DELIVERABLES field after CONTEXT
- 2026-10-02 — added meta-instruction: every project has a system design doc at docs/SYSTEM-DESIGN.md
- 2026-10-05 — added meta-instruction: applications include a settings button or tab
- 2026-10-08 — added meta-instruction: color-code tags by similarity (related share a hue family, each distinct)
- 2026-10-09 — added meta-instruction: apps that take files have an Upload button, drop anywhere, and paste
- 2026-10-13 — built SportsPred website: soccer + tennis predictions, odds over time, GitHub Pages deploy every 3 hours
- 2026-10-13 — added surface-specific tennis ratings (overall + hard/clay/grass Elo, blend fitted on results)
- 2026-10-13 — added ATP and WTA Finals predictions (round robin + semis; projected field until the draw)
- 2026-10-13 — added World Cup qualifying group predictions (qualify / playoff / top group; switches on when 2030 qualifiers are scheduled)
- 2026-10-13 — added a daily log of published odds, shown as dots alongside the replay (stored on the published site)
- 2026-10-13 — added the Mac app (native window around the live site, Mac menus and shortcuts, ⌘, settings)
- 2026-10-17 — 10 improvements: hourly updates, tennis cache fix, publish check, last-updated and stale notice, steady chart colours, season track record, calibration chart, chart table view, team/player search, Mac app offline mode (model experiments tried and not adopted are listed in docs/SYSTEM-DESIGN.md)
- 2026-10-18 — 10 more: current GitHub Actions (Node 24), zero axe accessibility issues, phone fixes, today's matches and biggest movers on the home page, matches grouped by day, add-to-home-screen with offline support, link previews and Share, 404 page, Mac File menu (Share, Copy Link, Open in Browser)
- 2026-10-18 — 10 more: league strength learned from European results (backtested), top-4 / relegation / top-8 / knockout odds, follow teams, time-aware Live status, Add to Calendar, legend toggles, keyboard search, publish check catches vanished competitions, Mac app reopens last page, new README screenshots
- 2026-10-20 — 15 more (5 technical: title-odds track record, real UEFA knockout bracket, per-competition fallback + empty-cache bug fix, CSP and escaping audit, integration tests; plus cache-busting found in testing. 10 cosmetic: flags, surface chips, loading placeholders, change since yesterday, live pill, table polish, card motion, home summary line, chart polish, updated label)
- 2026-10-20 — 10 more: match details (why, likely scores, head-to-head), what-if season simulator, team and player pages, matches that matter, upsets, compare-any-two tool, chart summaries for screen readers, CI smoke test, Mac Find a Team (⌘F); per-league scoring rates tested and not adopted
- 2026-10-21 — 10 more: competition page order (odds table first, what-if folded), projected tennis odds before the draw, reach-each-round chances, finishing-position grid, court ratings on player pages, team page form and next match, CSV download, sitemap, How It Works contents, shared result judging
