"""1.10042: how long the Rhino and the ship take to fill.

His ask, 19 Nov: "time how long it takes to fill the rhino with 72 as a full
hold then how long it will take to fill up the ship that the person is using
(check cargo)". Each Rhino load is timed from its first tonne to 72 t; the
STATUS box says when the Rhino will be full and when the ship will be, from
the rate of this load (or of the session), what the Rhino holds and what the
ship's hold has free by its own cargo capacity.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_filltimer.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import filltimer as FT        # noqa: E402
import statuslines as STL     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    return open(os.path.join(REPO, *parts), encoding="utf-8").read()


T0 = 1_800_000_000.0

print("== a Rhino load is timed from its first tonne to 72 t ==")
clock = FT.FillClock()
check("a full Rhino is 72 t", clock.full == 72 == FT.RHINO_FULL_T)
check("nothing timed to begin with", clock.last_load() is None and clock.average() is None
      and clock.this_load(T0) is None)
clock.note(0, T0)
for n in range(1, 73):
    clock.note(n, T0 + n * 20.0)     # a tonne every 20 s: 72 t in 24 minutes
check("72 t at a tonne every 20 s is a load of 24 minutes",
      clock.last_load() is not None and abs(clock.last_load() - 71 * 20.0) < 1, clock.last_load())
check("one load timed", clock.loads_timed() == 1)
check("a full Rhino is not counted twice while it sits full",
      (clock.note(72, T0 + 2000) or True) and clock.loads_timed() == 1)
clock.note(0, T0 + 2100)             # unloaded into the ship
check("after unloading nothing is being loaded", clock.this_load(T0 + 2100) is None)
for n in range(1, 73):
    clock.note(n, T0 + 2200 + n * 30.0)
check("the second load is timed too, and the average is of both",
      clock.loads_timed() == 2 and abs(clock.average() - (71 * 20.0 + 71 * 30.0) / 2) < 1, clock.average())
check("the last is the newest", abs(clock.last_load() - 71 * 30.0) < 1)
part = FT.FillClock()
part.note(0, T0)
for n in range(1, 31):
    part.note(n, T0 + n * 20.0)
part.note(0, T0 + 700)
check("a load unloaded before it was full is not a full load", part.loads_timed() == 0)
mid = FT.FillClock()
mid.note(10, T0)
check("joining a load already under way does not time it",
      (mid.note(11, T0 + 20) or True) and (all(mid.note(n, T0 + 20 * n) or True for n in range(12, 73)))
      and mid.loads_timed() == 0, mid.loads_timed())
check("but its rate is still measured", mid.rate(T0 + 20 * 72) is not None)
live = FT.FillClock()
live.note(0, T0)
for n in range(1, 13):
    live.note(n, T0 + n * 30.0)
elapsed, tonnes = live.this_load(T0 + 12 * 30.0)
check("the load under way: how long and how much", abs(elapsed - 11 * 30.0) < 1 and tonnes == 12, (elapsed, tonnes))
check("its rate in tonnes an hour", abs(live.rate(T0 + 12 * 30.0) - 11 / (11 * 30.0) * 3600) < 0.5,
      live.rate(T0 + 12 * 30.0))
young = FT.FillClock()
young.note(0, T0)
young.note(1, T0 + 10)
young.note(2, T0 + 20)
check("too little to go on is no rate", young.rate(T0 + 20) is None)
check("nothing known is nothing noted", (young.note(None, T0 + 30) or True) and young.this_load(T0 + 30) is not None)
many = FT.FillClock()
for load in range(8):
    base = T0 + load * 5000
    many.note(0, base)
    for n in range(1, 73):
        many.note(n, base + n * (10.0 + load))
check("the average is of the last five loads", many.loads_timed() == 8
      and abs(many.average() - sum(71 * (10.0 + k) for k in range(3, 8)) / 5) < 1, many.average())

print("== the words ==")
check("minutes", FT.span_text(24 * 60) == "24m" and FT.span_text(59) == "1m" and FT.span_text(20) == "<1m")
check("hours", FT.span_text(3 * 3600 + 10 * 60) == "3h 10m" and FT.span_text(3600) == "1h 00m")
check("nothing is nothing", FT.span_text(None) == "" and FT.span_text(-5) == "")
check("Rhino full in, with what it holds", FT.rhino_text(40, 180.0) == "in 11m  40/72 t", FT.rhino_text(40, 180.0))
check("Rhino full now", FT.rhino_text(72, 180.0) == "FULL  72/72 t" and FT.rhino_text(80, None) == "FULL  80/72 t")
check("with no rate yet, only what it holds", FT.rhino_text(10, None) == "10/72 t")
check("not in the journal, nothing", FT.rhino_text(None, 180.0) is None)
card = {"known": True, "tonnes": 300, "capacity": 1227}
check("ship full in: what the ship has free less what the Rhino holds, at the rate",
      FT.ship_text(card, 27, 180.0) == "in 5h 00m  300/1227 t", FT.ship_text(card, 27, 180.0))
check("a ship that will be full with what the Rhino holds is full",
      FT.ship_text({"known": True, "tonnes": 1200, "capacity": 1227}, 30, 180.0) == "FULL with this load")
check("a full ship is full", FT.ship_text({"known": True, "tonnes": 1227, "capacity": 1227}, 0, 180.0) == "FULL")
check("with no rate yet, what it holds", FT.ship_text(card, 0, None) == "300/1227 t")
check("a hold not seen yet, or a capacity not known, is nothing",
      FT.ship_text({"known": False}, 10, 180.0) is None
      and FT.ship_text({"known": True, "tonnes": 300, "capacity": None}, 10, 180.0) is None
      and FT.ship_text(None, 10, 180.0) is None)
check("the timed loads", FT.load_text(24 * 60, 26 * 60, 3) == "24m  avg 26m (3)"
      and FT.load_text(24 * 60, 24 * 60, 1) == "24m" and FT.load_text(None, None, 0) is None)

print("== on the STATUS box ==")
lines = STL.build({}, True, 0.3, False, 180.0, "Felicia Winters", 40,
                  fill={"rhino": FT.rhino_text(40, 180.0), "ship": FT.ship_text(card, 27, 180.0),
                        "load": FT.load_text(24 * 60, 26 * 60, 3)})
check("the three fill lines are on it", lines.get("rhino") == "in 11m  40/72 t"
      and lines.get("ship") == "in 5h 00m  300/1227 t" and lines.get("load") == "24m  avg 26m (3)", lines)
check("in their order, after the others",
      [r[0] for r in STL.rows(lines)] == ["SRV fuel", "t/h", "Merits", "Rhino full", "Ship full", "Rhino load"],
      [r[0] for r in STL.rows(lines)])
off = STL.build({"overlay_status_fill": False}, True, 0.3, False, 180.0, "", 0,
                fill={"rhino": "in 11m  40/72 t", "ship": "x", "load": "y"})
check("one switch turns them off", not ({"rhino", "ship", "load"} & set(off)), off)
check("lines with nothing to say are left out",
      not ({"ship", "load"} & set(STL.build({}, True, 0.3, False, 1.0, "", 0, fill={"rhino": "10/72 t"}))))
check("the switch is on unless turned off", STL.SWITCHES["fill"] == "overlay_status_fill")
brief = STL.compact(lines)[0]
check("as one short line too", "RHINO IN 11M" in brief and "SHIP IN 5H 00M" in brief, brief)
check("the old callers are unchanged", STL.build({}, True, 0.3, False, 9.0, "Felicia Winters", 40)
      == {"fuel": ("0.30 t", False), "tph": "9.0", "merits": "40"})

print("== wired into the app ==")
app = read("edsmt.py")
check("the app keeps a clock and feeds it what the Rhino holds",
      "FT.FillClock()" in app and "self.fill_clock.note(" in app)
check("and hands the fill lines to the STATUS box", "fill=self.fill_lines(" in app)
check("with a switch in Settings", '"overlay_status_fill"' in app and "STATUS line: Rhino and ship full in" in app)
check("filltimer is in both build specs", all('"filltimer"' in read("build", s)
                                               for s in ("EDSMT.spec", "EDSMT-onefile.spec")))
check("the guide says it", "Rhino full" in read("docs", "GUIDE.md") and "Ship full" in read("docs", "GUIDE.md"))

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
