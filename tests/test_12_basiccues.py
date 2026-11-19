"""1.2: when the new Basic lines are said (basiccues.py).

His approval, 19 Nov ("ok yeah", then "ok" for the Flight controller and
On-air wordings): value_top, value_best, rich_patch, sell_here, hold_full,
nearly_out, plenty_left, due_check, guide_far, landed_marked, pin_skipped,
import_done, ribbon_earned, live_on, live_off, rhino_full_soon,
ship_full_soon. The pure rules here; the app's wiring in test_12_basiclines.py.

    python tests/test_12_basiccues.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import basiccues as BC   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


PRICES = {"Platinum": 250000, "Painite": 300000, "Osmium": 200000, "Gold": 50000, "Silver": 40000,
          "Iridium": 150000, "Rhodplumsite": 180000, "Tritium": 60000}
price_of = lambda name: (PRICES.get(name, 0), "at Hub")

print("== high value: the five best-paying on the prices known ==")
check("the best of all", BC.value_line("Painite", price_of, PRICES) == "value_best")
check("one of the top five", BC.value_line("Osmium", price_of, PRICES) == "value_top"
      and BC.value_line("Iridium", price_of, PRICES) == "value_top")
check("sixth is nothing", BC.value_line("Tritium", price_of, PRICES) is None)
check("any case or spelling of the name", BC.value_line("painite", price_of, PRICES) == "value_best")
check("with no price known, nothing", BC.value_line("Unobtainium", price_of, PRICES) is None
      and BC.value_line("Painite", lambda n: (0, ""), PRICES) is None and BC.value_line("", price_of, PRICES) is None)
check("a price source that fails is nothing, not a fault",
      BC.value_line("Painite", lambda n: 1 / 0, PRICES) is None)
check("the top five, best first", BC.top_five(price_of, PRICES) == ["Painite", "Platinum", "Osmium",
                                                                      "Rhodplumsite", "Iridium"])

print("== how much is left ==")
check("little left: nearly out", BC.left_line((5, 20, 9, "crowd"), (110, 140, 9, "crowd")) == "nearly_out")
check("most of it: plenty left", BC.left_line((100, 130, 9, "crowd"), (110, 140, 9, "crowd")) == "plenty_left")
check("in between: nothing", BC.left_line((60, 70, 9, "crowd"), (110, 140, 9, "crowd")) is None)
check("not known: nothing", BC.left_line(None, (110, 140, 9, "crowd")) is None and BC.left_line((5, 9, 1, "x"), None) is None)

print("== once each ==")
once = BC.Once()
check("the first time, yes", once.first("value", "dep1") is True)
check("again, no", once.first("value", "dep1") is False)
check("another key, yes", once.first("value", "dep2") is True and once.first("left", "dep1") is True)
once.forget("value", "dep1")
check("forgotten, yes again", once.first("value", "dep1") is True)
once.forget_kind("left")
check("a whole kind forgotten", once.first("left", "dep1") is True)

print("== the Rhino and the ship, nearly full ==")
check("Rhino five minutes from full", BC.rhino_soon(57, 180.0) is True)       # 15 t at 180 t/h = 5 min
check("further off: not yet", BC.rhino_soon(40, 180.0) is False)
check("full already: not soon, full", BC.rhino_soon(72, 180.0) is False)
check("no rate: never", BC.rhino_soon(60, None) is False and BC.rhino_soon(None, 180.0) is False)
card = {"known": True, "tonnes": 1150, "capacity": 1227}
check("ship one Rhino load from full", BC.ship_soon(card, 10) is True)            # 67 t to fill
check("further off: not yet", BC.ship_soon(dict(card, tonnes=900), 10) is False)
check("full: not soon", BC.ship_soon(dict(card, tonnes=1227), 0) is False)
check("not known: never", BC.ship_soon({"known": False}, 10) is False and BC.ship_soon(None, 0) is False)
check("the Rhino full is a full hold", BC.hold_full(None, 72) is True and BC.hold_full(None, 71) is False)
check("the ship full is a full hold", BC.hold_full({"known": True, "tonnes": 1227, "capacity": 1227}, 0) is True
      and BC.hold_full(card, 0) is False)

print("== a rich patch ==")
rows = [{"id": "a", "patch": 1}, {"id": "b", "patch": 1}, {"id": "c", "patch": 1}, {"id": "d", "patch": 0}]
check("a deposit in the top patch of three or more", BC.rich_patch("a", rows) is True)
check("not in it: no", BC.rich_patch("d", rows) is False)
check("a top patch of two is not rich", BC.rich_patch("a", rows[:2]) is False)
check("nothing known: no", BC.rich_patch("a", []) is False and BC.rich_patch("", rows) is False)

print("== ribbons ==")
check("more ribbon steps than before: earned", BC.ribbon_new(5, {"earned": 6}) is True)
check("the same, or fewer: not", BC.ribbon_new(6, {"earned": 6}) is False and BC.ribbon_new(6, {"earned": 2}) is False)
check("the first look only notes it", BC.ribbon_new(None, {"earned": 6}) is False)
check("a broken answer: not", BC.ribbon_new(3, {"x": 1}) is False and BC.ribbon_new(3, None) is False)
check("what to keep", BC.ribbon_count({"earned": 6}) == 6 and BC.ribbon_count({"earned": "x"}) is None)

print("== selling here: the best price known for what makes most of the sale ==")
quote = {"station": "Hub", "parts": [{"commodity": "Platinum", "sell": 250000, "tonnes": 60},
                                     {"commodity": "Gold", "sell": 1000, "tonnes": 4}]}
check("as good as the best known: sell here", BC.sells_best(quote, price_of) is True)
check("better than the best known: sell here", BC.sells_best(
    {"parts": [{"commodity": "Platinum", "sell": 260000}]}, price_of) is True)
check("under the best known: not", BC.sells_best(
    {"parts": [{"commodity": "Platinum", "sell": 240000}]}, price_of) is False)
check("nothing known for it, or nothing sold: not", BC.sells_best(
    {"parts": [{"commodity": "Unobtainium", "sell": 9}]}, price_of) is False
      and BC.sells_best({"parts": []}, price_of) is False and BC.sells_best(None, price_of) is False)

print("== due a check: the nearest of yours on this body, within 2 km ==")
rows = [{"deposit": {"id": "a"}, "place": 0, "metres": 600.0},
        {"deposit": {"id": "b"}, "place": 0, "metres": 1500.0},
        {"deposit": {"id": "c"}, "place": 1, "metres": None}]
check("the nearest", BC.due_near(rows) == "a")
check("not the one you are on", BC.due_near(rows, skip="a") == "b")
check("none within 2 km: none", BC.due_near([{"deposit": {"id": "x"}, "place": 0, "metres": 2600.0}]) is None)
check("another body, or no distance: none", BC.due_near(rows[2:]) is None and BC.due_near([]) is None)

print("== the live-status switch ==")
check("the first look only notes it", BC.live_change(None, True) is None and BC.live_change(None, False) is None)
check("switched on", BC.live_change(False, True) == "live_on")
check("switched off", BC.live_change(True, False) == "live_off")
check("unchanged: nothing", BC.live_change(True, True) is None and BC.live_change(False, False) is None)

print("== the Rhino and the ship filling: each line once a load ==")
card = {"known": True, "capacity": 400, "tonnes": 100}
cues = BC.FillCues()
check("not in the Rhino: nothing", cues.step(None, card, 300.0) == [])
check("loading slowly: nothing", cues.step(10, card, 20.0) == [])
check("five minutes from full: said", cues.step(60, card, 300.0) == ["rhino_full_soon"])
check("and not again this load", cues.step(62, card, 300.0) == [])
check("72 t: hold full", cues.step(72, card, 300.0) == ["hold_full"])
check("and not again while it sits full", cues.step(72, card, 300.0) == [])
check("unloaded, a new load: nothing yet", cues.step(0, card, 300.0) == [])
check("the next load says them again", cues.step(61, card, 300.0) == ["rhino_full_soon"]
      and cues.step(72, card, 300.0) == ["hold_full"])
quiet = BC.FillCues()
check("with her own hold-full reaction playing, the Rhino's hold full is hers",
      quiet.step(72, card, 300.0, rhino_full_said=True) == [])
ship = BC.FillCues()
check("the ship one load from full: said once", ship.step(5, {"known": True, "capacity": 200,
                                                             "tonnes": 130}, 20.0) == ["ship_full_soon"]
      and ship.step(6, {"known": True, "capacity": 200, "tonnes": 130}, 20.0) == [])
full = BC.FillCues()
check("the ship's hold full: hold full", full.step(0, {"known": True, "capacity": 200, "tonnes": 200}, 20.0)
      == ["hold_full"])
check("its hold not known: only the Rhino's lines", BC.FillCues().step(72, None, 300.0) == ["hold_full"])

print("== the lines exist in every recorded voice ==")
import voice as VO   # noqa: E402
missing = [i for i in BC.LINE_IDS if i not in VO.LINES]
check("every new line is a line of the pack", not missing, missing)
check("seventeen of them", len(BC.LINE_IDS) == 17, len(BC.LINE_IDS))

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
