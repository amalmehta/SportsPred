"""SportsPred daily build: fetch results, rate teams and players, simulate, write site/data/*.json.

    python -m pipeline.build              # everything
    python -m pipeline.build --only tennis
"""
import argparse
import os
import time
import traceback

from . import soccer_build, tennis_build
from .common import SITE_DATA_DIR, now_iso, read_json, today, write_json


def summary(c):
    return {k: c.get(k) for k in ("id", "sport", "name", "group", "status", "season", "tour", "country",
                                  "start", "end", "favourite", "next_match", "champion", "slam", "updated")}


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
                  lambda c: c["sport"] == "soccer" and c["group"] != "international"),
        "international": (soccer_build.build_international, soccer_build.write, "soccer_international",
                          lambda c: c["group"] == "international"),
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
        write(comps)
        kept = {k: v for k, v in kept.items() if not belongs(v)}
        kept.update({c["id"]: summary(c) for c in comps})
        model[model_key] = m
        print("   %d competitions in %.0fs" % (len(comps), time.time() - t0))

    write_json(index_path, {"updated": now_iso(), "date": today_iso, "competitions": list(kept.values())}, compact=False)
    model["updated"] = now_iso()
    write_json(model_path, model, compact=False)
    if failed:
        raise SystemExit("failed: %s" % ", ".join(failed))


if __name__ == "__main__":
    main()
