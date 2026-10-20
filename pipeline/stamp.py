"""Cache-busting for deploys: point every page at its CSS/JS by content hash (app.js?v=1a2b3c4d).

GitHub Pages lets browsers keep files for 10 minutes, so without this a visitor could get a new page
script with yesterday's shared script and a broken page. Run in CI just before publishing:

    python -m pipeline.stamp site
"""
import hashlib
import os
import re
import sys

ASSET = re.compile(r'((?:src|href)=")(assets/[\w./-]+\.(?:js|css))(?:\?v=[^"]*)?(")')


def stamp(site_dir):
    hashes = {}

    def version(rel):
        if rel not in hashes:
            with open(os.path.join(site_dir, rel), "rb") as f:
                hashes[rel] = hashlib.sha256(f.read()).hexdigest()[:10]
        return hashes[rel]

    changed = []
    for name in sorted(os.listdir(site_dir)):
        if not name.endswith(".html"):
            continue
        path = os.path.join(site_dir, name)
        with open(path, encoding="utf-8") as f:
            html = f.read()
        new = ASSET.sub(lambda m: "%s%s?v=%s%s" % (m.group(1), m.group(2), version(m.group(2)), m.group(3)), html)
        if new != html:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            changed.append(name)
    return changed


if __name__ == "__main__":
    print("stamped:", ", ".join(stamp(sys.argv[1] if len(sys.argv) > 1 else "site")) or "nothing")
