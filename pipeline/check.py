"""Sanity-check site/data before it's published. Any problem fails the run, so the live site keeps
its last good version instead of showing broken predictions.

    python -m pipeline.check
"""
import os
import sys

from .common import SITE_DATA_DIR, read_json

TOL = 0.02


def problems_in(c):
    """Everything wrong with one competition file (an empty list means it's fine)."""
    out = []
    name = c.get("name") or c.get("id")
    table = c.get("table") or []
    key = "player" if c.get("sport") == "tennis" else "team"
    for r in table:
        for k in ("p_win", "p_qualify", "p_playoff", "p_sf"):
            v = r.get(k)
            if v is not None and not (0.0 <= v <= 1.0):
                out.append("%s: %s has %s = %s" % (name, r.get(key), k, v))
    awaiting = c.get("sport") == "tennis" and not c.get("favourite")  # no draw yet
    total = sum(r.get("p_win", 0.0) for r in table)
    if c.get("format") == "qualifying":
        groups = len({r.get("group") for r in table})
        if abs(total - groups) > TOL * groups:
            out.append("%s: group-winner chances add up to %.3f, not %d" % (name, total, groups))
        direct = (c.get("slots") or {}).get("direct", 0)
        q = sum(r.get("p_qualify", 0.0) for r in table)
        if direct and abs(q - groups * direct) > TOL * groups * direct:
            out.append("%s: qualifying chances add up to %.3f, not %d" % (name, q, groups * direct))
    elif not awaiting:
        if not table:
            out.append("%s: no teams or players" % name)
        elif abs(total - 1.0) > TOL:
            out.append("%s: title chances add up to %.3f, not 1" % (name, total))
    for m in c.get("upcoming") or []:
        p = m.get("p")
        if isinstance(p, list) and abs(sum(p) - 1.0) > TOL:
            out.append("%s: %s v %s chances add up to %.3f" % (name, m.get("home"), m.get("away"), sum(p)))
        elif isinstance(p, (int, float)) and not (0.0 <= p <= 1.0):
            out.append("%s: %s v %s chance %s" % (name, m.get("a"), m.get("b"), p))
    return out


def check(data_dir=SITE_DATA_DIR):
    index = read_json(os.path.join(data_dir, "index.json"))
    if not index or not index.get("competitions"):
        return ["index.json is missing or lists no competitions"]
    out = []
    sports = {c["sport"] for c in index["competitions"]}
    for sport in ("soccer", "tennis"):
        if sport not in sports:
            out.append("no %s competitions in index.json" % sport)
    for summary in index["competitions"]:
        c = read_json(os.path.join(data_dir, summary["sport"], summary["id"] + ".json"))
        if c is None:
            out.append("%s: listed in index.json but its file is missing" % summary["id"])
            continue
        out.extend(problems_in(c))
    return out


def main():
    found = check()
    for p in found:
        print("PROBLEM:", p)
    if found:
        sys.exit("%d problem(s): not publishing" % len(found))
    print("site/data looks good")


if __name__ == "__main__":
    main()
