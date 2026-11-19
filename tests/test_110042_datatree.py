"""1.10042: the data window's rows - systems, grounds, folding locations,
top patches, a worked-out deposit's tonnes and the deposit card.

My sites becomes the one data window a commander asked for: the systems
with their counts and totals, the bodies of a system grouped by the kind of
ground they are, the locations on a body that fold open and shut with a
line about each and how far it is from you, a location's deposits top
patch first and worked out last, a worked-out deposit saying what it gave,
and a card with everything about one deposit. sitetree.py makes the rows;
this checks them without a window.

    python tests/test_110042_datatree.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import survey as SV        # noqa: E402
import sitetree as ST      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


R = 1000000.0      # a body 1,000 km in radius: 0.01 degrees is 174.5 m
store = SV.Survey(tempfile.mkdtemp(prefix="edsmt-datatree-"))
store.set_location("Ega", "Ega A 1", "1", lat=10.0, lon=20.0, radius_m=R,
                   commodities=["Iridium", "Rhodplumsite"])
store.set_location("Ega", "Ega A 1", "2", lat=-5.0, lon=40.0, radius_m=R,
                   commodities=["Thortveitite", "Bromellite"])
store.set_location("Ega", "Ega B 3", "4", lat=1.0, lon=1.0, radius_m=R,
                   commodities=["Gold"])
for logged in store.locations:
    logged["planet_class"] = "Metal rich body" if logged["body"] == "Ega A 1" else ""
    logged["volcanism"] = "major silicate vapour geysers volcanism" if logged["body"] == "Ega A 1" else ""


def deposit(**row):
    row.setdefault("system", "Ega")
    row.setdefault("body", "Ega A 1")
    row.setdefault("location", "1")
    row.setdefault("density", "High")
    row.setdefault("amount", "High")
    row.setdefault("recorded", "2026-11-01T10:00:00Z")
    return store.add_deposit(**row)


# Location 1: a knot of three near the centre (4 + 2 + 3 rigs, within 400 m
# of each other), a 6-rig deposit 5 km out - a top patch on its own - a
# 1-rig one 1.5 km south of the knot, and one worked out after giving 300t
# then 340t.
a = deposit(commodity="Iridium", rigs="4", lat="10.0", lon="20.0", mined="Iridium:120;Gold:9")
b = deposit(commodity="Rhodplumsite", rigs="2", lat="10.002", lon="20.0")
c = deposit(commodity="Iridium", rigs="3", lat="10.0", lon="20.002")
far = deposit(commodity="Rhodplumsite", rigs="6", lat="10.3", lon="20.0")
lone = deposit(commodity="Iridium", rigs="1", lat="9.914", lon="20.0")
spent = deposit(commodity="Iridium", rigs="4", amount="Depleted", lat="10.001", lon="20.001",
                cycles="2026-10-01=300;2026-10-20=340", depleted_at="2026-10-20T11:00:00Z")
# Location 2, and a deposit with no position at all.
deposit(location="2", commodity="Thortveitite", rigs="5", lat="-5.0", lon="40.0", mined="Thortveitite:40")
blind = deposit(location="2", commodity="Bromellite", rigs="2", lat="", lon="")
# Another system altogether.
store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5", commodity="Iridium",
                  rigs="2", density="Medium", amount="Low", lat="1.0", lon="1.0",
                  cycles="2026-09-01=50", recorded="2026-09-20T10:00:00Z")

print("== C1: the systems, with their counts and totals ==")
rows = ST.systems(store)
ega = next(r for r in rows if r["system"] == "Ega")
check("each system counts the rigs still to be had (worked-out ones left out)",
      ega["rigs"] == 4 + 2 + 3 + 6 + 1 + 5 + 2, ega)
check("and the tonnes mined there, every time worked out included",
      ega["mined"] == 120 + 300 + 340 + 40, ega)
hr = next(r for r in rows if r["system"] == "HR 7280")
check("a system elsewhere counts its own", (hr["locations"], hr["deposits"], hr["rigs"], hr["mined"])
      == (1, 1, 2, 50), hr)
total = ST.totals(rows)
check("the totals carry locations, deposits, rigs and tonnes mined",
      (total["locations"], total["deposits"], total["rigs"], total["mined"]) == (4, 9, 25, 850), total)
check("and read as a line", ST.totals_text(total) ==
      "2 systems - 4 locations - 9 deposits - 25 rigs - 850t mined", ST.totals_text(total))
check("one of each is said in the singular",
      ST.totals_text({"systems": 1, "bodies": 1, "locations": 1, "deposits": 1, "rigs": 0, "mined": 0})
      == "1 system - 1 location - 1 deposit", ST.totals_text(ST.totals(rows[:1])))
rows = ST.systems(store, ["Thortveitite"])
check("the material filter counts only what carries it", [(r["system"], r["deposits"], r["rigs"], r["mined"])
      for r in rows] == [("Ega", 1, 5, 40)], rows)

print("== C2: the bodies of a system, grouped by their ground ==")
groups = ST.grounds(store, "Ega")
check("one group a kind of ground, the one with most deposits first, unknown last",
      [g["ground"] for g in groups] == ["Metal rich body, major silicate vapour geysers", ST.UNKNOWN_GROUND],
      [g["ground"] for g in groups])
check("each group holds its bodies and their counts",
      [b["body"] for b in groups[0]["bodies"]] == ["Ega A 1"] and groups[0]["deposits"] == 8
      and groups[1]["bodies"][0]["body"] == "Ega B 3", groups)
book = {("Ega", "Ega B 3"): ("Rocky body", "")}
groups = ST.grounds(store, "Ega", lookup=lambda system, body: book.get((system, body)))
check("a body its records do not describe takes its ground from the app's book of bodies",
      [g["ground"] for g in groups] == ["Metal rich body, major silicate vapour geysers", "Rocky body"],
      [g["ground"] for g in groups])
check("a book that fails is no answer, not an error",
      ST.grounds(store, "Ega", lookup=lambda s, b: 1 / 0)[-1]["ground"] == ST.UNKNOWN_GROUND)
flat = ST.ground_rows(groups)
check("as one list: a heading row a ground, then its bodies",
      [(r["kind"], r.get("body") or r["ground"]) for r in flat] ==
      [("ground", "Metal rich body, major silicate vapour geysers"), ("body", "Ega A 1"),
       ("ground", "Rocky body"), ("body", "Ega B 3")], flat)
check("the filter follows down to the grounds", [g["ground"] for g in ST.grounds(store, "Ega", ["Gold"])]
      == [ST.UNKNOWN_GROUND], ST.grounds(store, "Ega", ["Gold"]))

print("== C11: a location's deposits, top patch first, worked out last ==")
rows = ST.deposits(store, "Ega", "Ega A 1", "1")
order = [r["id"] for r in rows]
check("the top patch first, the deposit at its heart leading, then the rest of it nearest that one",
      order[:3] == [a["id"], c["id"], b["id"]], [(r["commodity"], r["rigs"], r["patch"]) for r in rows])
check("the deposits of the top patch carry its number", [r["patch"] for r in rows[:3]] == [1, 1, 1],
      [r["patch"] for r in rows])
check("then the next patch: six rigs on one deposit is a patch of its own",
      order[3] == far["id"] and rows[3]["patch"] == 2, [(r["commodity"], r["rigs"], r["patch"]) for r in rows])
check("then the deposits in no patch, most rigs first",
      order[4] == lone["id"] and rows[4]["patch"] == 0, [(r["commodity"], r["rigs"], r["patch"]) for r in rows])
check("and the worked-out one last", order[-1] == spent["id"], order)
rows2 = ST.deposits(store, "Ega", "Ega A 1")
check("with no location named, location by location", [r["location"] for r in rows2] ==
      ["1"] * 6 + ["2"] * 2, [r["location"] for r in rows2])
check("a patch smaller than a ship's worth is no patch: most rigs first",
      [r["commodity"] for r in rows2[6:]] == ["Thortveitite", "Bromellite"], rows2[6:])
check("without the body's radius nothing is measured: most rigs first, worked out last",
      [r["rigs"] for r in ST.patch_order([dict(r) for r in rows])] == [6, 4, 3, 2, 1, 4]
      and ST.patch_order([dict(r) for r in rows])[-1]["depleted"], ST.patch_order([dict(r) for r in rows]))
wide = ST.deposits(store, "Ega", "Ega A 1", "1", radius_m=2500)
check("a top patch is the map's own: a wider setting takes the 1-rig one 1.5 km off into the first",
      [r["id"] for r in wide if r["patch"] == 1] == [a["id"], c["id"], b["id"], lone["id"]],
      [(r["commodity"], r["rigs"], r["patch"]) for r in wide])

print("== C13: a worked-out deposit says what it gave ==")
row = rows[-1]
check("the row knows the tonnes of its last time", row["gave"] == 340, row["gave"])
check("and the Est. left cell says it", ST.left_text(row["left"], True, row["gave"]) == "worked out (340t)")
check("never worked out with a count: just worked out", ST.left_text(None, True) == "worked out")
check("a deposit not worked out has none", rows[0]["gave"] is None)
check("last_cycle reads the newest", ST.last_cycle(spent) == 340 and ST.last_cycle(a) is None)

print("== C3: the locations on a body, folding ==")
you = {"system": "Ega", "body": "Ega A 1", "lat": 10.0, "lon": 20.01, "radius_m": R}
fold = ST.fold_rows(store, "Ega", "Ega A 1", opened=["1"], you=you)
kinds = [r["kind"] for r in fold]
check("a line for each location, the open one's deposits under it",
      kinds == ["location"] + ["deposit"] * 6 + ["location"], kinds)
line = fold[0]
check("each line says what is there in one line",
      line["line"] == "Location 1 - 6 deposits, 16 rigs - Iridium, Rhodplumsite - 1 worked out",
      line["line"])
check("and how far it is from you, to its nearest deposit",
      line["away"][0] == "m" and abs(line["away"][1] - SV.surface_range_m(10.0, 20.01, 10.0, 20.002, R)) < 0.01,
      line["away"])
check("which reads as words", ST.away_text(("m", 820.0), lambda m: "%.0f m" % m) == "820 m from you")
shut = fold[-1]
check("a folded location shows none of its deposits, only its line",
      shut["open"] is False and shut["line"].startswith("Location 2 - 2 deposits, 7 rigs"), shut["line"])
check("open them all", [r["kind"] for r in ST.fold_rows(store, "Ega", "Ega A 1", opened=["1", "2"])].count("deposit") == 8)
check("fold them all", [r["kind"] for r in ST.fold_rows(store, "Ega", "Ega A 1")] == ["location", "location"])
check("on another body there is no distance", ST.fold_rows(
    store, "Ega", "Ega A 1", you=dict(you, body="Ega B 3"))[0]["away"] == (None, None))
ly = ST.fold_rows(store, "HR 7280", "HR 7280 A 3", you=dict(you, ly=lambda system: 12.36))[0]
check("in another system it is light years, when the stars are known",
      ly["away"] == ("ly", 12.36) and ST.away_text(ly["away"], str) == "12.4 Ly from you", ly["away"])
check("and nothing when they are not", ST.fold_rows(
    store, "HR 7280", "HR 7280 A 3", you=dict(you, ly=lambda system: None))[0]["away"] == (None, None))
empty = ST.fold_rows(store, "Ega", "Ega B 3")[0]
check("a logged signal with nothing marked says what it offers",
      empty["line"] == "Location 4 - nothing marked - offers Gold", empty["line"])
check("and is measured to where it was logged", ST.fold_rows(
    store, "Ega", "Ega B 3", you=dict(you, body="Ega B 3", lat=1.0, lon=1.0))[0]["away"] == ("m", 0.0))
check("the filter follows into the folds", [r["commodity"] for r in ST.fold_rows(
    store, "Ega", "Ega A 1", opened=["1"], picked=["Rhodplumsite"]) if r["kind"] == "deposit"]
      == ["Rhodplumsite", "Rhodplumsite"])

print("== C5: the deposit card ==")
row = next(r for r in ST.deposits(store, "Ega", "Ega A 1", "1") if r["id"] == a["id"])
here = dict(you, lat=9.99, lon=20.0, heading=90.0)
card = ST.card(row, here, {"iridium": 250000}, lambda m: "%.0f m" % m)
lines = dict(card["lines"])
check("its title: commodity and location", card["title"] == "Iridium - location 1", card["title"])
check("where: system and body", lines["System"] == "Ega" and lines["Body"] == "Ega A 1")
check("its coordinates, to six places", lines["Position"] == "10.000000, 20.000000", lines["Position"])
check("which way and how far it is from you, and the turn",
      lines["From you"] == "175 m N 000 - left", lines["From you"])
check("rigs, amount and density", (lines["Rigs"], lines["Amount"], lines["Density"]) == ("4", "High", "High"))
check("the tonnes this time, by-products beside", lines["Mined this time"] == "120t (and Gold 9t)",
      lines["Mined this time"])
check("what is thought to be left, and what that rests on",
      lines["Left"].startswith("est. 180-220t - From 2 times a deposit of yours"), lines["Left"])
check("the price known", lines["Price"] == "250,000 Cr/t", lines["Price"])
check("when it was marked", lines["Marked"] == "2026-11-01 10:00 UTC", lines["Marked"])
check("and its state", lines["State"] == "active" and card["depleted"] is False)
dead = ST.card(next(r for r in ST.deposits(store, "Ega", "Ega A 1", "1") if r["id"] == spent["id"]))
lines = dict(dead["lines"])
check("a worked-out one: what it gave, and since when",
      lines["Left"] == "worked out (340t)" and lines["State"] == "worked out since 2026-10-20", lines)
check("away from its body the card says so", dict(ST.card(row, dict(you, body="Ega B 3")))["lines"] and
      dict(ST.card(row, dict(you, body="Ega B 3"))["lines"])["From you"] == "not on this body - you are at Ega B 3")
check("with no idea where you are, it says that",
      dict(ST.card(row)["lines"])["From you"] == "not known - where you are is not known yet")
nowhere = next(r for r in ST.deposits(store, "Ega", "Ega A 1", "2") if r["id"] == blind["id"])
check("a deposit with no position says so, in its place and as the reason",
      dict(ST.card(nowhere, you)["lines"])["Position"] == "no position recorded"
      and dict(ST.card(nowhere, you)["lines"])["From you"].startswith("not known - no position"))

print("== it reads, and changes nothing ==")
before = ([dict(d) for d in store.deposits], [dict(r) for r in store.locations])
ST.systems(store), ST.grounds(store, "Ega"), ST.fold_rows(store, "Ega", "Ega A 1", ["1", "2"], you=you)
ST.card(row, here)
check("the records are as they were",
      before == ([dict(d) for d in store.deposits], [dict(r) for r in store.locations]))

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
