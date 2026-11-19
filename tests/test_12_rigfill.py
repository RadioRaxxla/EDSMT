"""1.2: how full each rig is, counted from the journal (rigfill.py).

His ask (1.10043 list, R1, "do all these" 19 Nov): say when a rig is full.
The journal has no rig event; it writes one MiningRefined a tonne, and a rig
holds 12 (his screenshot shows x/12). Exact when each rig is on its own
commodity, an estimate (shown with ~) when rigs share one. Nothing here reads
the screen.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_12_rigfill.py
"""
import inspect
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
# Never the real data folder: the app is loaded below.
import tempfile   # noqa: E402
os.environ["LOCALAPPDATA"] = os.path.join(tempfile.mkdtemp(prefix="edsmt-12-"), "appdata")

import rigfill as RF   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


T0 = 1_800_000_000


def stamp(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def tonne(what, t, srv="7", lat=10.0, lon=20.0, **kw):
    note = {"event": "Refined", "commodity": what, "when": stamp(t), "srv_id": srv,
            "lat": lat, "lon": lon, "radius_m": 1500000.0, "in_srv": True,
            "system": "Ega", "body": "Ega 1"}
    note.update(kw)
    return note


print("== one rig on its commodity: exact ==")
rigs = [{"n": 1, "lat": 10.0, "lon": 20.0, "at": T0, "commodity": "Platinum", "srv": "7"},
        {"n": 2, "lat": 10.001, "lon": 20.0, "at": T0, "commodity": "Gold", "srv": "7"}]
check("a rig holds 12", RF.RIG_HOLDS_T == 12)
check("nothing counted to begin with", RF.count(rigs[0]) == 0 and RF.text(rigs[0]) == "0/12")
got = RF.credit(rigs, tonne("Platinum", T0 + 60))
check("a tonne of its commodity is put against it", got is rigs[0] and RF.count(rigs[0]) == 1)
check("the other rig is not touched", RF.count(rigs[1]) == 0)
for k in range(11):
    RF.credit(rigs, tonne("platinum", T0 + 70 + k))
check("twelve: full, and exact", RF.is_full(rigs[0]) and RF.text(rigs[0]) == "12/12", RF.text(rigs[0]))
check("a full rig takes no more", RF.credit(rigs, tonne("Platinum", T0 + 200)) is None
      and RF.count(rigs[0]) == 12)
check("a by-product or another commodity: no rig", RF.credit(rigs, tonne("Water", T0 + 60)) is None)
check("a tonne from before the rig went down: not its",
      RF.credit(rigs, tonne("Gold", T0 - 600)) is None and RF.count(rigs[1]) == 0)
check("another Rhino's tonne: not its", RF.credit(rigs, tonne("Gold", T0 + 60, srv="8")) is None)
check("out of the Rhino: nothing", RF.credit(rigs, tonne("Gold", T0 + 60, in_srv=False)) is None)
check("a broken note: nothing", RF.credit(rigs, None) is None and RF.credit(rigs, {}) is None
      and RF.credit([], tonne("Gold", T0 + 60)) is None)

print("== two rigs on one commodity: the nearest, and marked as an estimate ==")
pair = [{"n": 3, "lat": 10.0, "lon": 20.0, "at": T0, "commodity": "Osmium", "srv": "7"},
        {"n": 4, "lat": 10.01, "lon": 20.0, "at": T0, "commodity": "Osmium", "srv": "7"}]
check("refined by rig 4: rig 4", RF.credit(pair, tonne("Osmium", T0 + 60, lat=10.0099)) is pair[1])
check("both shown as estimates", RF.text(pair[0]) == "~0/12" and RF.text(pair[1]) == "~1/12",
      (RF.text(pair[0]), RF.text(pair[1])))
nowhere = [{"n": 5, "lat": 1.0, "lon": 1.0, "at": T0, "commodity": "Silver", "srv": "7", "t": 4},
           {"n": 6, "lat": 1.1, "lon": 1.0, "at": T0, "commodity": "Silver", "srv": "7", "t": 2}]
check("no position: the one with fewest", RF.credit(nowhere, tonne("Silver", T0 + 60, radius_m=0)) is nowhere[1])
full_one = [{"n": 1, "lat": 10.0, "lon": 20.0, "at": T0, "commodity": "Tin", "srv": "7", "t": 12},
            {"n": 2, "lat": 11.0, "lon": 20.0, "at": T0, "commodity": "Tin", "srv": "7", "t": 3}]
check("the nearest full: the next one takes it", RF.credit(full_one, tonne("Tin", T0 + 60)) is full_one[1])

print("== in the app ==")
try:
    import edsmt as A
except Exception as exc:   # noqa: BLE001
    print("  FAIL  the app did not load: %s" % exc)
    sys.exit(1)

app = A.EDSMT.__new__(A.EDSMT)
app.settings = dict(A.DEFAULT_SETTINGS)
flashes, lines, notes = [], [], []
app.flash = lambda *a, **kw: flashes.append(a)
app.say = lambda *a, **kw: lines.append(a[0])
app.trouble = lambda *a, **kw: None
app.refresh_rigs_note = lambda: notes.append(1)
app.rig_label = lambda rig: str(rig.get("n"))
app.rigs_at = {"system": "Ega", "body": "Ega 1", "rhinos": ["7"],
               "rigs": [{"n": 1, "lat": 10.0, "lon": 20.0, "at": T0, "commodity": "Platinum", "srv": "7"}]}
for k in range(11):
    app.rig_fill(tonne("Platinum", T0 + 60 + k))
check("each tonne counted on the rig", app.rigs_at["rigs"][0].get("t") == 11 and not flashes)
check("and the rigs note redrawn", len(notes) == 11)
app.rig_fill(tonne("Platinum", T0 + 100))
check("the twelfth: RIG 1 FULL over the game", flashes and flashes[-1][0] == "RIG 1 FULL", flashes)
check("and in words, saying it is counted from the journal",
      lines and "Rig 1 full" in lines[-1] and "counted from the journal" in lines[-1], lines)
check("on another body: nothing", app.rig_fill(tonne("Platinum", T0 + 60, body="Ega 2")) is None)
check("each refined tonne goes to it", "self.rig_fill(note)" in inspect.getsource(A.EDSMT.tick))
check("the rigs note shows each rig's count", "RF.text(" in inspect.getsource(A.EDSMT.refresh_rigs_note))
check("nothing reads the screen", "ImageGrab" not in open(os.path.join(REPO, "rigfill.py")).read())
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    check("%s bundles rigfill" % spec, '"rigfill"' in open(os.path.join(REPO, "build", spec)).read())
check("the whole suite runs this", "test_12_rigfill.py" in open(os.path.join(HERE, "run_all.py")).read())

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
