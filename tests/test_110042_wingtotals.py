"""1.10042 (#173): Rhino totals on Earnings, and the wing line when the wing
link is on. The wing link carries no tonnes, so the line is your own Rhinos'
total, said plainly.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_wingtotals.py
"""
import faulthandler
import io
import json
import os
import sys

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import rhinototals as RT   # noqa: E402
import wingmates as WM     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


def session(**rhinos):
    return {"rhinos": json.dumps({k: {"label": k, "mined": "Platinum:%d" % v, "rigs": 1}
                                  for k, v in rhinos.items()})}


rows = [session(**{"Rhino A": 40, "Rhino B": 10}), session(**{"Rhino A": 25}), {"rhinos": ""}, {}]
found = RT.totals(rows)
check("tonnes and sessions across Rhinos", found["tonnes"] == 75 and found["sessions"] == 2, found)
check("each Rhino, biggest first", [(p["label"], p["tonnes"], p["sessions"]) for p in found["rhinos"]]
      == [("Rhino A", 65, 2), ("Rhino B", 10, 1)], found["rhinos"])
check("sessions that do not know their Rhinos are not counted", RT.totals([{}])["sessions"] == 0)
check("nothing to say with no sessions", RT.line([], True) == "" and RT.line([{}], False) == "")
on = RT.line(rows, True)
check("wing link on: your Rhinos' total, labelled", on.startswith("Wing: your Rhinos 75 t over 2 sessions")
      and "Rhino A 65 t" in on, on)
check("it says wingmates' tonnes are not shared", "not shared" in on and "only yours" in on, on)
check("wing link on with one Rhino still says it", RT.line([session(**{"Rhino A": 9})], True).startswith("Wing: your Rhinos 9 t over 1 session")
      and "(" not in RT.line([session(**{"Rhino A": 9})], True).split(".")[0])
off = RT.line(rows, False)
check("wing link off: the split between your Rhinos", off == "Your Rhinos: Rhino A 65 t, Rhino B 10 t", off)
check("wing link off, one Rhino: nothing", RT.line([session(**{"Rhino A": 9})], False) == "")
check("a damaged row is skipped, not a crash", RT.totals([{"rhinos": "{bad"}, None])["sessions"] == 0)
check("what the wing link carries today holds no tonnes",
      not any(w in read("wingmates.py").lower() for w in ("tonnes_total", "credits_total")))
src = read("edsmt.py")
check("Earnings shows it under the all-time line", "RT.line(self._rows" in src)
check("rhinototals is in both build specs", all('"rhinototals"' in read("build", s)
                                                for s in ("EDSMT.spec", "EDSMT-onefile.spec")))
check("the guide says it", "wing** line" in read("docs", "GUIDE.md").lower())
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
