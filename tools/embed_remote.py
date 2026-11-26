"""Copy remote/AirSense_Remote.pyw into desktop/AirSense.pyw (one file = the whole app).

    python tools/embed_remote.py          → update desktop/AirSense.pyw
    python tools/embed_remote.py --check  → exit 1 if they differ (used by GitHub Actions)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "remote", "AirSense_Remote.pyw")
DST = os.path.join(ROOT, "desktop", "AirSense.pyw")
BEGIN = "REMOTE_SRC = r'''"
END = "'''  # <<< REMOTE_SRC END"

src = open(SRC, encoding="utf-8").read()
if "'''" in src or src.endswith("\\"):
    sys.exit("remote source cannot contain ''' (it is embedded in a r''' string)")
dst = open(DST, encoding="utf-8").read()
a = dst.index(BEGIN) + len(BEGIN)
b = dst.index(END)
new = dst[:a] + src + dst[b:]
if "--check" in sys.argv:
    if new != dst:
        sys.exit("✖ desktop/AirSense.pyw is not in sync with remote/AirSense_Remote.pyw → run python tools/embed_remote.py")
    print("✔ embedded AirSense Remote is in sync")
else:
    if new != dst:
        open(DST, "w", encoding="utf-8", newline="\n").write(new)
        print("✔ desktop/AirSense.pyw updated")
    else:
        print("= already in sync")
