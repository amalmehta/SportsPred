"""Fetch soccer results and fixtures from ESPN's public scoreboard feed, plus the international archive."""
import csv
import io
import os

from . import config
from .common import DATA_DIR, ESPN, fetch, read_json, today, write_json

SOCCER_CACHE = os.path.join(DATA_DIR, "soccer")


def parse_event(e, slug):
    """One ESPN event -> a compact match dict, or None if it isn't a two-team match."""
    comp = (e.get("competitions") or [{}])[0]
    teams = comp.get("competitors") or []
    if len(teams) != 2:
        return None
    home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
    away = next((t for t in teams if t is not home), teams[1])
    st = (e.get("status") or {}).get("type") or {}
    state = st.get("state")
    final = state == "post" and st.get("completed", False)
    if state == "post" and not final:
        status = "postponed"
    else:
        status = "final" if final else ("live" if state == "in" else "scheduled")

    def score(t):
        try:
            return int(float(t.get("score")))
        except (TypeError, ValueError):
            return None

    m = {
        "id": e.get("id"), "slug": slug, "date": e.get("date"),
        "season": (e.get("season") or {}).get("year"), "stage": (e.get("season") or {}).get("slug", ""),
        "home_id": home["team"]["id"], "home": home["team"].get("displayName"),
        "away_id": away["team"]["id"], "away": away["team"].get("displayName"),
        "neutral": bool(comp.get("neutralSite")), "status": status,
    }
    if final:
        m["hg"], m["ag"] = score(home), score(away)
        if m["hg"] is None or m["ag"] is None:
            return None
        if home.get("winner"):
            m["winner"] = "home"
        elif away.get("winner"):
            m["winner"] = "away"
        else:
            m["winner"] = "draw"
        m["detail"] = st.get("name", "")
    return m


def fetch_year(slug, year):
    url = "%s/site/v2/sports/soccer/%s/scoreboard?dates=%d&limit=1000" % (ESPN, slug, year)
    data = fetch(url)
    out = []
    for e in data.get("events", []):
        m = parse_event(e, slug)
        if m:
            out.append(m)
    return out


def load_slug(slug, first_year, last_year):
    """All matches for a competition. Finished calendar years are cached on disk; recent years are refetched."""
    matches = []
    this_year = today().year
    for y in range(first_year, last_year + 1):
        path = os.path.join(SOCCER_CACHE, slug, "%d.json" % y)
        cached = read_json(path)
        if cached is not None and y < this_year:
            matches.extend(cached)
            continue
        try:
            got = fetch_year(slug, y)
        except RuntimeError as err:
            print("  ! %s %d: %s" % (slug, y, err))
            got = cached or []
        if y < this_year:
            write_json(path, got)
        matches.extend(got)
    # de-duplicate (events can straddle year queries)
    seen, uniq = set(), []
    for m in sorted(matches, key=lambda m: m["date"]):
        if m["id"] not in seen:
            seen.add(m["id"])
            uniq.append(m)
    return uniq


def fetch_groups(slug):
    """Group tables from ESPN standings: {group name: [team ids]}."""
    try:
        data = fetch("%s/v2/sports/soccer/%s/standings" % (ESPN, slug))
    except RuntimeError:
        return {}
    groups = {}
    for child in data.get("children", []):
        entries = (child.get("standings") or {}).get("entries", [])
        groups[child.get("name", "")] = [e["team"]["id"] for e in entries]
    return groups


def load_international_results():
    """International results archive (martj42/international_results), refreshed each run."""
    path = os.path.join(SOCCER_CACHE, "international_results.csv")
    try:
        text = fetch(config.INTERNATIONAL_RESULTS_URL, as_json=False)
        os.makedirs(SOCCER_CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except RuntimeError as err:
        print("  ! international results: %s (using cached copy)" % err)
        with open(path, encoding="utf-8") as f:
            text = f.read()
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if r["date"] < "1990-01-01" or r["home_score"] in ("", "NA"):
            continue
        rows.append({
            "date": r["date"], "home": r["home_team"], "away": r["away_team"],
            "hg": int(r["home_score"]), "ag": int(r["away_score"]),
            "tournament": r["tournament"], "neutral": r["neutral"].upper() == "TRUE",
        })
    return rows
