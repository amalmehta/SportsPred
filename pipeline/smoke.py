"""Smoke test of the built site before publishing: every page's local links resolve, every competition and
team page listed has its file, and every script parses. Fails the run on any problem.

    python -m pipeline.smoke site
"""
import os
import re
import shutil
import subprocess
import sys

from .common import read_json

LINK = re.compile(r'(?:src|href)="(?!https?:|#|mailto:)([^"?#]+)')


def problems(site):
    out = []
    pages = [f for f in os.listdir(site) if f.endswith(".html")]
    for page in pages:
        html = open(os.path.join(site, page), encoding="utf-8").read()
        base = "" if page != "404.html" else ""  # 404 uses <base href="/SportsPred/">, same layout as the site root
        for target in LINK.findall(html):
            path = os.path.join(site, base, target)
            if target.endswith("/") or target in ("./", ""):
                continue
            if not os.path.exists(path):
                out.append("%s links to %s, which doesn't exist" % (page, target))
    data = os.path.join(site, "data")
    for c in (read_json(os.path.join(data, "index.json"), {}) or {}).get("competitions", []):
        if not os.path.exists(os.path.join(data, c["sport"], c["id"] + ".json")):
            out.append("index lists %s but its file is missing" % c["id"])
    for name, fid in (read_json(os.path.join(data, "teams.json"), {}) or {}).items():
        if not os.path.exists(os.path.join(data, "teams", fid + ".json")):
            out.append("team page for %s is missing" % name)
    node = shutil.which("node")
    if node:
        for root, _, files in os.walk(site):
            for f in files:
                if f.endswith(".js"):
                    r = subprocess.run([node, "--check", os.path.join(root, f)], capture_output=True, text=True)
                    if r.returncode:
                        out.append("%s doesn't parse: %s" % (f, (r.stderr.strip().splitlines() or [""])[-1]))
    return out


if __name__ == "__main__":
    found = problems(sys.argv[1] if len(sys.argv) > 1 else "site")
    for p in found:
        print("PROBLEM:", p)
    if found:
        sys.exit("%d problem(s): not publishing" % len(found))
    print("site smoke test passed")
