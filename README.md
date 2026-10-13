# SportsPred

Live winner predictions for soccer leagues and tennis tournaments, worked out from past results and refreshed every three hours.

![Home page: every competition with its favourite and their chance to win](docs/images/Home%20Page.jpg)

![Premier League title odds over the season](docs/images/Title%20Odds%20Over%20Time.jpg)

![Upcoming match predictions and recent results against the model's call](docs/images/Match%20Predictions.jpg)

```mermaid
flowchart LR
  A[ESPN results & fixtures<br/>International results archive] --> B[Elo ratings]
  B --> C[Match chances]
  C --> D[10,000 simulated seasons and draws]
  D --> E[Website: title odds, odds over time, match picks]
```

**Covers:** Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, Europa League, international tournaments while they're on, plus ATP and WTA Grand Slams and 1000-level events.

- **Live site:** https://amalmehta.github.io/SportsPred/
- [How to set it up, run it and use it](docs/INSTRUCTIONS.md)
- [System design](docs/SYSTEM-DESIGN.md)
- [What's where](docs/FILE-STRUCTURE.md)
- [How the predictions work](https://amalmehta.github.io/SportsPred/how.html)
