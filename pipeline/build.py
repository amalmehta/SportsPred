"""SportsPred daily build: fetch results, rate teams and players, simulate, write site/data/*.json.

    python -m pipeline.build              # everything
    python -m pipeline.build --only tennis
"""
import argparse
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
import time
import traceback

from xml.sax.saxutils import escape

from . import config, live_log, soccer_build, tennis_build
from .common import DATA_DIR, SITE_DATA_DIR, now_iso, read_json, today, write_json

HISTORY_DIR = os.path.join(DATA_DIR, "histories")  # rating histories per part (kept between runs, not published)


def slug(name):
    """'Borussia Mönchengladbach' -> 'borussia-monchengladbach' (for team page file names)."""
    ascii_ = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "team"


def summary(c):
    return {k: c.get(k) for k in ("id", "sport", "name", "group", "status", "season", "tour", "country",
                                  "start", "end", "favourite", "second", "next_match", "champion", "slam", "surface", "projected", "format", "stale", "updated")}


def search_index(summaries):
    """Every team and player on the site, for the home page's search: name -> where they appear."""
    found = {}
    for s in summaries:
        c = read_json(os.path.join(SITE_DATA_DIR, s["sport"], s["id"] + ".json"))
        if not c:
            continue
        key = "p_qualify" if c.get("format") == "qualifying" else "p_win"
        who = "player" if c["sport"] == "tennis" else "team"
        for r in c.get("table", []):
            found.setdefault(r[who], []).append({
                "id": c["id"], "sport": c["sport"], "name": c["name"], "p": r.get(key, 0.0),
                "what": "qualify" if key == "p_qualify" else "win", "out": r.get("alive") is False,
                "status": c.get("status")})
    return [{"n": n, "in": sorted(v, key=lambda e: -e["p"])} for n, v in sorted(found.items())]


def today_digest(summaries, hours=36, min_move=0.03):
    """Home page digest: the next day and a half of matches everywhere, and the biggest odds moves
    between the last two days the site published (from each competition's live log)."""
    now = datetime.now(timezone.utc)
    soon = (now + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%MZ")
    since = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%MZ")  # keep games that may still be on
    matches, movers, upsets, big = [], [], [], []
    week_ahead = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%MZ")
    for s in summaries:
        c = read_json(os.path.join(SITE_DATA_DIR, s["sport"], s["id"] + ".json"))
        if not c:
            continue
        where = {"id": c["id"], "sport": c["sport"], "comp": c["name"], "group": c.get("group"), "country": c.get("country")}
        for m in c.get("upcoming", []):
            if since <= (m.get("date") or "") <= soon:
                matches.append(dict(m, **where))
        live = c.get("live") or []
        if len(live) >= 2:
            before, after = live[-2], live[-1]
            for team in set(before["p"]) & set(after["p"]):  # a newly listed entrant isn't a move
                a, b = before["p"].get(team, 0.0), after["p"].get(team, 0.0)
                if abs(b - a) >= min_move:
                    movers.append(dict(where, team=team, before=a, after=b, since=before["date"],
                                       what="qualify" if c.get("format") == "qualifying" else "win"))
        for sw in c.get("swings", []):
            if sw.get("date") and now.strftime("%Y-%m-%dT%H:%MZ") <= sw["date"] <= week_ahead:
                big.append(dict(where, **sw))
        # upsets: finished in the last week, and the result was one we gave less than 25%
        week = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%MZ")
        for m in c.get("recent", []):
            if (m.get("date") or "") < week:
                continue
            if c["sport"] == "tennis":
                p_happened = m["p"] if m["w"] == 0 else 1 - m["p"]
                winner, loser = (m["a"], m["b"]) if m["w"] == 0 else (m["b"], m["a"])
                text = "%s beat %s" % (winner, loser)
            else:
                o = 0 if m["hg"] > m["ag"] else (1 if m["hg"] == m["ag"] else 2)
                p_happened = m["p"][o]
                text = "%s %d–%d %s" % (m["home"], m["hg"], m["ag"], m["away"])
            if p_happened < 0.25:
                upsets.append(dict(where, date=m["date"], text=text, p=round(p_happened, 3)))
    matches.sort(key=lambda m: m["date"])
    movers.sort(key=lambda m: -abs(m["after"] - m["before"]))
    upsets.sort(key=lambda u: u["p"])
    big.sort(key=lambda x: -x["swing"])
    return {"updated": now_iso(), "matches": matches, "movers": movers[:8], "upsets": upsets[:6], "big": big[:4]}


def team_pages(summaries, histories, out_dir=None):
    """One small file per team or player on the site: chances everywhere, rating history, next and recent games."""
    out_dir = out_dir or os.path.join(SITE_DATA_DIR, "teams")
    people = {}
    for s in summaries:
        c = read_json(os.path.join(SITE_DATA_DIR, s["sport"], s["id"] + ".json"))
        if not c:
            continue
        who = "player" if c["sport"] == "tennis" else "team"
        key = "p_qualify" if c.get("format") == "qualifying" else "p_win"
        part = "tennis" if c["sport"] == "tennis" else ("international" if c.get("group") in ("international", "qualifying") else "clubs")
        where = {"id": c["id"], "sport": c["sport"], "name": c["name"], "group": c.get("group"), "status": c.get("status")}
        hard = {x["team"]: i + 1 for i, x in enumerate(c.get("run_in") or [])}  # 1 = hardest games left
        for r in c.get("table", []):
            p = people.setdefault((c["sport"], r[who]), {"name": r[who], "sport": c["sport"], "part": part, "flag": r.get("flag"),
                                                         "comps": [], "upcoming": [], "recent": []})
            extra = {k: r[k] for k in ("sure", "xpts", "pts", "p_adv", "p_ko", "reach") if r.get(k) is not None}
            if r[who] in hard:
                extra["run_in"] = [hard[r[who]], len(hard)]
            p["comps"].append(dict(where, p=r.get(key, 0.0), what="qualify" if key == "p_qualify" else "win",
                                   p_top=r.get("p_top"), p_drop=r.get("p_drop"), out=r.get("alive") is False,
                                   top=(c.get("places") or {}).get("top"), **extra))
        for kind in ("upcoming", "recent"):
            for m in c.get(kind, []):
                for n in ((m.get("home"), m.get("away")) if c["sport"] == "soccer" else (m.get("a"), m.get("b"))):
                    if (c["sport"], n) in people:
                        people[(c["sport"], n)][kind].append(dict(m, comp=c["name"], comp_id=c["id"]))
    index = {}
    for (sport, name), p in people.items():
        hist = (histories.get(p["part"]) or {})
        if p["part"] == "tennis":
            hist = dict((histories.get("tennis") or {}).get("atp", {}), **(histories.get("tennis") or {}).get("wta", {}))
        p["rating"] = hist.get(name, [])[-80:]
        p["upcoming"].sort(key=lambda m: m["date"])
        p["recent"].sort(key=lambda m: m["date"], reverse=True)
        p["upcoming"], p["recent"] = p["upcoming"][:10], p["recent"][:10]
        fid = "%s-%s" % (sport, slug(name))
        write_json(os.path.join(out_dir, fid + ".json"), p)
        index[name + "|" + sport] = fid
    return index


def write_sitemap(summaries, pages, site_dir=None):
    """sitemap.xml: home, How It Works, every competition and every team / player page."""
    site_dir = site_dir or os.path.dirname(SITE_DATA_DIR)
    base = config.SITE_URL or ""
    urls = [base, base + "how.html"]
    urls += [base + "competition.html?sport=%s&id=%s" % (c["sport"], c["id"]) for c in summaries]
    urls += [base + "team.html?id=" + fid for fid in sorted(pages.values())]
    body = "".join("  <url><loc>%s</loc></url>\n" % escape(u) for u in urls)
    with open(os.path.join(site_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % body)
    return len(urls)


def write_feed(digest, summaries, site_dir=None, now=None):
    """feed.xml (Atom): the week's upsets, the day's biggest odds moves and recent champions, for feed readers."""
    site_dir = site_dir or os.path.dirname(SITE_DATA_DIR)
    base = config.SITE_URL or ""
    now = now or now_iso()
    stamp = lambda iso: (iso[:16] if len(iso) >= 16 else iso[:10] + "T12:00") + ":00Z"
    page = lambda sport, cid: base + "competition.html?sport=%s&id=%s" % (sport, cid)
    entries = []
    for u in digest.get("upsets", []):
        entries.append(("upset-%s-%s" % (u["id"], u["date"]), "%s upset: %s" % (u["comp"], u["text"]), u["date"],
                        page(u["sport"], u["id"]), "We gave that result %d%% before the match." % round(u["p"] * 100)))
    for m in digest.get("movers", []):
        up = m["after"] > m["before"]
        entries.append(("move-%s-%s-%s" % (m["id"], slug(m["team"]), now[:10]),
                        "%s: %s %s to %d%% to %s" % (m["comp"], m["team"], "up" if up else "down", round(m["after"] * 100),
                                                     m["what"]),
                        now, page(m["sport"], m["id"]),
                        "From %d%% the day before." % round(m["before"] * 100)))
    recent = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    for c in summaries:
        if c.get("status") == "finished" and c.get("champion") and (c.get("end") or "")[:10] >= recent:
            entries.append(("champion-%s" % c["id"], "%s: won by %s" % (c["name"], c["champion"]), c["end"],
                            page(c["sport"], c["id"]), "%s are the champions." % c["champion"] if c["sport"] == "soccer"
                            else "%s is the champion." % c["champion"]))
    entries.sort(key=lambda e: e[2], reverse=True)
    body = "".join(
        "  <entry>\n    <id>tag:sportspred,2026:%s</id>\n    <title>%s</title>\n    <updated>%s</updated>\n"
        "    <link href=\"%s\"/>\n    <summary>%s</summary>\n  </entry>\n"
        % (escape(eid), escape(title), stamp(when), escape(link, {'"': "&quot;"}), escape(text))
        for eid, title, when, link, text in entries[:40])
    with open(os.path.join(site_dir, "feed.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
                "  <title>SportsPred: upsets and big moves</title>\n  <id>%s</id>\n  <updated>%s</updated>\n"
                '  <link href="%s"/>\n  <link rel="self" href="%sfeed.xml"/>\n  <author><name>SportsPred</name></author>\n%s</feed>\n'
                % (escape(base or "tag:sportspred,2026:feed"), stamp(now), escape(base), escape(base), body))
    return len(entries[:40])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["clubs", "international", "tennis"], action="append")
    args = ap.parse_args(argv)
    parts = args.only or ["clubs", "international", "tennis"]
    today_iso = today().isoformat()
    index_path = os.path.join(SITE_DATA_DIR, "index.json")
    model_path = os.path.join(SITE_DATA_DIR, "model.json")
    index = read_json(index_path, {"competitions": []})
    model = read_json(model_path, {})
    kept = {c["id"]: c for c in index.get("competitions", [])}

    steps = {
        "clubs": (soccer_build.build_clubs, soccer_build.write, "soccer_clubs",
                  lambda c: c["sport"] == "soccer" and c["group"] in ("domestic", "european")),
        "international": (soccer_build.build_international, soccer_build.write, "soccer_international",
                          lambda c: c["group"] in ("international", "qualifying")),
        "tennis": (tennis_build.build, tennis_build.write, "tennis", lambda c: c["sport"] == "tennis"),
    }
    failed = []
    for name in parts:
        build, write, model_key, belongs = steps[name]
        t0 = time.time()
        print("== %s" % name)
        try:
            comps, m = build(today_iso)
        except Exception:
            # keep yesterday's predictions for this part rather than publishing nothing
            traceback.print_exc()
            failed.append(name)
            continue
        write(live_log.attach(comps, today_iso))
        kept = {k: v for k, v in kept.items() if not belongs(v)}
        kept.update({c["id"]: summary(c) for c in comps})
        # rating histories / all ratings travel with the model but aren't published in model.json
        extras = {k: m.pop(k) for k in ("_histories", "_ratings") if k in m}
        for sub in ("atp", "wta"):
            if isinstance(m.get(sub), dict):
                extras.setdefault("_histories", {})[sub] = m[sub].pop("_histories", {})
                extras.setdefault("_ratings", {})[sub] = m[sub].pop("_ratings", {})
        write_json(os.path.join(HISTORY_DIR, name + ".json"), extras.get("_histories", {}))
        ratings_file = os.path.join(SITE_DATA_DIR, "ratings.json")
        ratings = read_json(ratings_file, {})
        if name == "tennis":
            for sub in ("atp", "wta"):
                ratings[sub] = {"weight": m[sub].get("surface_weight"), "players": extras["_ratings"].get(sub, {})}
        else:
            ratings["soccer" if name == "clubs" else "international"] = {
                "hfa": m.get("hfa"), "base": m.get("goals_base"), "slope": m.get("slope"), "rho": m.get("rho", 0), "teams": extras.get("_ratings", {})}
        write_json(ratings_file, ratings)
        model[model_key] = m
        print("   %d competitions in %.0fs" % (len(comps), time.time() - t0))

    write_json(index_path, {"updated": now_iso(), "date": today_iso, "competitions": list(kept.values())}, compact=False)
    model["updated"] = now_iso()
    write_json(model_path, model, compact=False)
    write_json(os.path.join(SITE_DATA_DIR, "search.json"), search_index(kept.values()))
    digest = today_digest(kept.values())
    write_json(os.path.join(SITE_DATA_DIR, "today.json"), digest, compact=False)
    write_feed(digest, kept.values())
    histories = {p: read_json(os.path.join(HISTORY_DIR, p + ".json"), {}) for p in ("clubs", "international", "tennis")}
    pages = team_pages(kept.values(), histories)
    write_json(os.path.join(SITE_DATA_DIR, "teams.json"), pages)
    write_sitemap(kept.values(), pages)
    if failed:
        raise SystemExit("failed: %s" % ", ".join(failed))


if __name__ == "__main__":
    main()
