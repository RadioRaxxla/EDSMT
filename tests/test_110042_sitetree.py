"""1.10042: everything recorded, read as system, body, location, deposit.

The records were all there and a commander had to go to four places to see
them: the rail, My sites, Where to land and a line of details. sitetree.py
turns the same records into the rows one window needs - the systems, the
bodies of one, the locations on a body, and the deposits in a location with
their rigs, where they are from the location's centre, what was mined and
what is thought to be left.

    python tests/test_110042_sitetree.py
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


RADIUS = 1000000.0      # a body 1,000 km in radius: one degree is 17.45 km
store = SV.Survey(tempfile.mkdtemp(prefix="edsmt-sitetree-"))

# Two systems. Ega A 1 has two locations; Col 285 has one find whose signal
# was never logged.
store.set_location("Ega", "Ega A 1", "1", lat=10.0, lon=20.0, radius_m=RADIUS,
                   commodities=["Iridium", "Rhodplumsite"])
store.set_location("Ega", "Ega A 1", "2", lat=-5.0, lon=40.0, radius_m=RADIUS,
                   commodities=["Thortveitite"], depleted=["Thortveitite"])
store.set_location("Ega", "Ega B 3 a", "10", lat=1.0, lon=1.0, radius_m=RADIUS,
                   commodities=["Iridium"])
for logged in store.locations:
    logged["recorded"] = "2026-10-01T09:00:00Z"     # logging stamps the present
north = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Iridium",
                          rigs="4", density="High", amount="High", lat="10.01", lon="20.0",
                          mined="Iridium:120;Gold:9", recorded="2026-11-01T10:00:00Z")
east = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Rhodplumsite",
                         rigs="6", density="Low", amount="Medium", lat="10.0", lon="20.05",
                         recorded="2026-11-02T10:00:00Z")
spent = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Iridium",
                          rigs="4", density="High", amount="Depleted", lat="10.0", lon="20.0",
                          cycles="2026-10-01=300;2026-10-20=340", recorded="2026-10-20T10:00:00Z")
again = store.add_deposit(system="Ega", body="Ega A 1", location="2", commodity="Thortveitite",
                          rigs="3", density="Medium", amount="Low", lat="-5.0", lon="40.002",
                          mined="Thortveitite:40", cycles="2026-10-05=200",
                          recorded="2026-11-03T10:00:00Z")
loose = store.add_deposit(system="Col 285 Sector AB-C d1-2", body="Col 285 Sector AB-C d1-2 4",
                          location="7", commodity="Iridium", rigs="4", density="High",
                          amount="High", lat="3.0", lon="3.0", recorded="2026-09-01T10:00:00Z")

print("== the systems ==")
rows = ST.systems(store)
check("one row a system, in name order",
      [r["system"] for r in rows] == ["Col 285 Sector AB-C d1-2", "Ega"], rows)
ega = rows[1]
check("with its bodies, locations and deposits counted",
      (ega["bodies"], ega["locations"], ega["deposits"]) == (2, 3, 4), ega)
check("and how many deposits are not worked out", ega["intact"] == 3, ega)
check("and when it was last added to", ega["last"].startswith("2026-11-03"), ega)
check("a find whose signal was never logged still counts its location",
      (rows[0]["bodies"], rows[0]["locations"], rows[0]["deposits"]) == (1, 1, 1), rows[0])
check("the totals across them (and, from the data window, the rigs and tonnes)", ST.totals(rows) ==
      {"systems": 2, "bodies": 3, "locations": 4, "deposits": 5, "rigs": 17, "mined": 1000},
      ST.totals(rows))

print("== the bodies of a system ==")
rows = ST.bodies(store, "ega")
check("one row a body, in the order the game numbers them",
      [r["body"] for r in rows] == ["Ega A 1", "Ega B 3 a"], rows)
check("the short name leaves the system's off", rows[0]["short"] == "A 1", rows[0])
check("locations and deposits counted", (rows[0]["locations"], rows[0]["deposits"]) == (2, 4), rows[0])
check("what is there to mine now, most first",
      list(rows[0]["types"].items()) == [("Iridium", 1), ("Rhodplumsite", 1), ("Thortveitite", 1)],
      rows[0]["types"])
check("a body with a logged signal and nothing marked is a row too",
      (rows[1]["locations"], rows[1]["deposits"]) == (1, 0), rows[1])

print("== the locations on a body ==")
rows = ST.locations(store, "Ega", "Ega A 1")
check("one row a location, by number", [r["location"] for r in rows] == ["1", "2"], rows)
one = rows[0]
check("deposits, and those not worked out", (one["deposits"], one["intact"]) == (3, 2), one)
check("what the signal offers and what has been found", one["offers"] == ["Iridium", "Rhodplumsite"]
      and one["types"] == {"Iridium": 1, "Rhodplumsite": 1}, one)
check("rigs to be had, worked-out deposits left out", one["rigs"] == 10, one)
check("whether its centre is known", one["centre"] == (10.0, 20.0) and rows[1]["centre"] == (-5.0, 40.0), one)
check("what the game says is already worked out", rows[1]["worked_out"] == ["Thortveitite"], rows[1])
rows = ST.locations(store, "Col 285 Sector AB-C d1-2", "Col 285 Sector AB-C d1-2 4")
check("a location that was never logged has no centre", rows[0]["location"] == "7"
      and rows[0]["centre"] is None and rows[0]["logged"] is False, rows)

print("== the deposits in a location ==")
rows = ST.deposits(store, "Ega", "Ega A 1", "1")
check("one row a deposit", len(rows) == 3, rows)
# The data window (1.10042, C11): top patch first and worked out last, where
# this used to be nearest the centre first. The two live ones are 860 m
# apart: one patch of 10 rigs, from the deposit at its heart.
check("top patch first, worked out last", [r["id"] for r in rows] == [north["id"], east["id"], spent["id"]],
      [(r["commodity"], r["metres"]) for r in rows])
by_id = {r["id"]: r for r in rows}
n = by_id[north["id"]]
check("how far from the centre: 0.01 degrees north is 175 m",
      abs(n["metres"] - 174.5) < 0.5 and abs(n["bearing"] - 0.0) < 0.01, (n["metres"], n["bearing"]))
e = by_id[east["id"]]
check("and which way: due east", abs(e["bearing"] - 90.0) < 0.5 and 850 < e["metres"] < 870,
      (e["metres"], e["bearing"]))
check("rigs as a number, 0 when not known", (n["rigs"], e["rigs"]) == (4, 6), (n["rigs"], e["rigs"]))
check("its own tonnes this time, by-products beside and not added in",
      n["mined"] == 120 and n["by"] == {"Gold": 9}, (n["mined"], n["by"]))
check("a worked-out deposit says so", by_id[spent["id"]]["depleted"] is True and n["depleted"] is False)
check("the row carries the record itself, for the buttons", n["deposit"] is north)
rows = ST.deposits(store, "Ega", "Ega A 1")
check("with no location named: every deposit on the body, location by location",
      [r["location"] for r in rows] == ["1", "1", "1", "2"], [r["location"] for r in rows])
rows = ST.deposits(store, "Col 285 Sector AB-C d1-2", "Col 285 Sector AB-C d1-2 4", "7")
check("with no centre there is no distance, and it is not an error",
      rows[0]["metres"] is None and rows[0]["bearing"] is None, rows[0])

print("== what a deposit holds and what is left ==")
check("worked out before: what it gave each time is what it holds",
      ST.holds(again) == (200, 200, 1, "measured"), ST.holds(again))
check("and what is left is that less what has come off it since",
      ST.left(again) == (160, 160, 1, "measured"), ST.left(again))
check("never worked out, with a like deposit of your own that was: an estimate from it",
      ST.holds(north, store.deposits) == (300, 340, 2, "yours"), ST.holds(north, store.deposits))
check("less what has come off this one", ST.left(north, store.deposits) == (180, 220, 2, "yours"),
      ST.left(north, store.deposits))
check("nothing like it worked out: not known, rather than a guess",
      ST.holds(east, store.deposits) is None and ST.left(east, store.deposits) is None)
check("a worked-out deposit has nothing left to estimate",
      ST.left(spent, store.deposits) is None and ST.holds(spent) == (300, 340, 2, "measured"))
over = dict(again, mined="Thortveitite:260")
check("more mined than it ever held: nothing left, never a minus",
      ST.left(over) == (0, 0, 1, "measured"), ST.left(over))
rows = ST.deposits(store, "Ega", "Ega A 1", "1")
check("the rows carry both", {r["id"]: r["left"] for r in rows}[north["id"]] == (180, 220, 2, "yours"))

print("== the words for them ==")
metres = lambda m: "%.0f m" % m     # noqa: E731 - the window hands in its own
check("where: distance, compass point and bearing", ST.where_text(174.6, 0.0, metres) == "175 m N 000",
      ST.where_text(174.6, 0.0, metres))
check("at the centre", ST.where_text(0.4, 123.0, metres) == "at the centre")
check("no centre logged", ST.where_text(None, None, metres) == "-")
check("left, a range", ST.left_text((180, 220, 2, "yours")) == "est. 180-220t", ST.left_text((180, 220, 2, "yours")))
check("left, one figure, measured on this deposit", ST.left_text((160, 160, 1, "measured")) == "about 160t")
# 1.10042 (D1): the words, not a dash.
check("not known", ST.left_text(None) == "not measured yet")
check("worked out", ST.left_text(None, depleted=True) == "worked out")
check("what it rests on, for the tip",
      ST.left_basis((180, 220, 2, "yours"), north) ==
      "From 2 times a deposit of yours with 4 rigs and High density was worked out.",
      ST.left_basis((180, 220, 2, "yours"), north))
check("and when it is this deposit's own",
      ST.left_basis((160, 160, 1, "measured"), again) == "From the 1 time this deposit was worked out.",
      ST.left_basis((160, 160, 1, "measured"), again))

print("== one material, and the whole tree follows ==")
rows = ST.systems(store, ["Thortveitite"])
check("only the systems that have it", [r["system"] for r in rows] == ["Ega"], rows)
check("counting only what has it", (rows[0]["bodies"], rows[0]["locations"], rows[0]["deposits"]) == (1, 1, 1), rows[0])
rows = ST.bodies(store, "Ega", ["thortveitite"])
check("only the bodies", [r["body"] for r in rows] == ["Ega A 1"], rows)
rows = ST.locations(store, "Ega", "Ega A 1", ["Thortveitite"])
check("only the locations", [r["location"] for r in rows] == ["2"], rows)
rows = ST.deposits(store, "Ega", "Ega A 1", picked=["Iridium", "Thortveitite"])
check("several picked: any of them", [r["commodity"] for r in rows] == ["Iridium", "Iridium", "Thortveitite"],
      [r["commodity"] for r in rows])
rows = ST.locations(store, "Ega", "Ega B 3 a", ["Iridium"])
check("a location that only offers it, with nothing marked yet, still shows",
      [r["location"] for r in rows] == ["10"], rows)
check("nothing picked is everything", len(ST.deposits(store, "Ega", "Ega A 1", picked=[])) == 4)

print("== it reads, and changes nothing ==")
before = ([dict(d) for d in store.deposits], [dict(r) for r in store.locations])
ST.systems(store), ST.bodies(store, "Ega"), ST.locations(store, "Ega", "Ega A 1")
ST.deposits(store, "Ega", "Ega A 1"), ST.left(north, store.deposits)
check("the records are as they were",
      before == ([dict(d) for d in store.deposits], [dict(r) for r in store.locations]))
source = open(os.path.join(REPO, "sitetree.py"), encoding="utf-8").read()
check("it imports no window", "import edsmt" not in source and "tkinter" not in source)

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
