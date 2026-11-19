"""1.10042: the parts the data window is built from, without a window.

  - your own up and down marks on any logged location, kept on this PC
    (ownmarks.py): on, off again, and where each puts a location in the list;
  - Guide me there to any deposit on any body (farguide.py): what is kept,
    the plain words for where the guiding stands, and why a deposit cannot
    be guided to;
  - "Worth mining only" in the materials picker (materials.worth_mining);
  - the map picture's row for each deposit with its position, and the top
    patches circled (mapimage.py);
  - a map picture of any site, and of each surveyed area of a body
    (sitetree.picture_inputs, sitetree.areas).

    python tests/test_110042_dataparts.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import survey as SV        # noqa: E402
import coverage as CV      # noqa: E402
import materials as MT     # noqa: E402
import mapimage as MI      # noqa: E402
import sitetree as ST      # noqa: E402
import ownmarks as OM      # noqa: E402
import farguide as FG      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


TMP = tempfile.mkdtemp(prefix="edsmt-dataparts-")
R = 1000000.0

print("== C12: your own marks, kept on this PC ==")
path = os.path.join(TMP, "records", OM.FILE_NAME)
book = OM.OwnMarks(path)
check("a location starts with no mark", book.mine("Ega", "Ega A 1", "1") == "")
check("press up: it is marked up", book.press("Ega", "Ega A 1", "1", OM.UP) == OM.UP)
check("however the names are spaced or cased, it is the same location",
      book.mine(" ega ", "EGA  A 1", "1") == OM.UP)
check("press down: the mark changes", book.press("Ega", "Ega A 1", "1", OM.DOWN) == OM.DOWN)
check("press the lit one again: the mark comes off", book.press("Ega", "Ega A 1", "1", OM.DOWN) == ""
      and book.marks == {})
check("a location with no number can be marked too", book.press("Ega", "Ega B 3", "", OM.UP) == OM.UP)
check("anything else is not a mark", book.set("Ega", "Ega A 1", "1", "good") is False
      and book.set("", "Ega A 1", "1", OM.UP) is False)
book.press("Ega", "Ega A 1", "2", OM.DOWN)
check("saved", book.save() and os.path.isfile(path))
again = OM.OwnMarks(path)
check("and read back", again.load() and again.mine("Ega", "Ega A 1", "2") == OM.DOWN
      and again.mine("Ega", "Ega B 3") == OM.UP)
kept = json.load(open(path, encoding="utf-8"))
check("the file holds the marks and nothing to send", set(kept) == {"marks"}
      and all("sent" not in entry for entry in kept["marks"].values()), kept)
with open(path, "w", encoding="utf-8") as handle:
    handle.write("{ not json")
check("a damaged file is an empty book, not an error", OM.OwnMarks(path).load() is False)
check("up lists first, down last, the unmarked between",
      sorted(["", OM.DOWN, OM.UP], key=OM.rank) == [OM.UP, "", OM.DOWN])
buttons = OM.buttons(again, "Ega", "Ega A 1", "2")
check("two buttons a location, yours lit", [(mark, lit) for _text, mark, lit in buttons]
      == [(OM.UP, False), (OM.DOWN, True)] and buttons[0][0].endswith("up"), buttons)
source = open(os.path.join(REPO, "ownmarks.py"), encoding="utf-8").read()
check("it sends nothing and opens no window", "urllib" not in source and "tkinter" not in source
      and "import edsmt" not in source and "edonline" not in source)

print("== C10: guide me there, to any deposit on any body ==")
deposit = {"id": "d-1", "system": "Ega", "body": "Ega A 1", "location": "1",
           "commodity": "Iridium", "lat": "10.0", "lon": "20.0"}
target = FG.target_of(deposit)
check("what is kept: which deposit, where it is", target == {
    "id": "d-1", "system": "Ega", "body": "Ega A 1", "location": "1", "commodity": "Iridium",
    "lat": 10.0, "lon": 20.0}, target)
check("it survives a trip through the settings file",
      FG.from_settings(json.loads(json.dumps(FG.to_settings(target)))) == target)
check("junk in the settings is no target", FG.from_settings("x") is None and FG.from_settings({}) is None
      and FG.from_settings(dict(target, lat="north")) is None and FG.to_settings(None) is None)
state, words = FG.status(target, "Ega", "Ega A 1", "d-1")
check("on its body: the map and the overlay point at it", state == "on"
      and words == "Guiding you to the Iridium deposit (location 1) - the map and the overlay "
                   "point at it until you get there.", words)
state, words = FG.status(target, "Ega", "Ega B 3", "d-1")
check("on another body of the system: it says which body to be on", state == "body"
      and "on Ega A 1" in words and "You are at Ega B 3" in words and "once you are on A 1" in words, words)
state, words = FG.status(target, "HR 7280", "HR 7280 A 3", "d-1")
check("in another system: where it is, and what to do next", state == "system"
      and "on Ega A 1, in Ega" in words and "You are in HR 7280" in words
      and "Jump there and land on A 1" in words, words)
check("with no idea where you are it still says where it is",
      FG.status(target, "", "", "d-1")[0] == "system" and "You are in" not in FG.status(target, "", "", "d-1")[1])
check("it is kept until you get there: once the overlay lets go, it is off",
      FG.status(target, "Ega", "Ega A 1", None)[0] == "off")
check("and off when another deposit was picked", FG.status(target, "Ega", "Ega A 1", "d-2")[0] == "off")
check("nothing picked is off, and says how to start", FG.status(None)[0] == "off"
      and "Guide me there" in FG.status(None)[1])
check("on its body or not", FG.arrived_on_body(target, "ega", "EGA A 1")
      and not FG.arrived_on_body(target, "Ega", "Ega B 3") and not FG.arrived_on_body(None, "Ega", "Ega A 1"))
check("a deposit with a position can be guided to", FG.why_not(deposit) == "")
check("no position recorded: said in plain words", "No position was recorded" in FG.why_not(dict(deposit, lat=""))
      and FG.target_of(dict(deposit, lat="")) is None, FG.why_not(dict(deposit, lat="")))
check("no body recorded: said", "No body was recorded" in FG.why_not(dict(deposit, body="")))
check("not one of your records: said", "not in your records" in FG.why_not({"commodity": "Gold"})
      and "not in your records" in FG.why_not(None))

print("== C15: worth mining only ==")
names = ["Iridium", "Olivine", "Magnesite", "Thortveitite", "No such stuff"]
worth = MT.worth_mining(names)
check("from the published prices: the ones over the line", worth == ["Iridium", "Thortveitite"], worth)
check("a market you opened has the last word", MT.worth_mining(names, {"olivine": 150000, "iridium": 90000})
      == ["Olivine", "Thortveitite"], MT.worth_mining(names, {"olivine": 150000, "iridium": 90000}))
check("a material with no price known is left out, not guessed at", "No such stuff" not in worth)
check("the line is a number of credits a tonne", isinstance(MT.WORTH_LINE_CR, int) and MT.WORTH_LINE_CR > 0)

print("== C16: the map picture - a row a deposit with its position, top patches circled ==")
store = SV.Survey(os.path.join(TMP, "store"))
store.set_location("Ega", "Ega A 1", "1", lat=10.0, lon=20.0, radius_m=R, commodities=["Iridium"])
spots = [("Iridium", "4", "10.0", "20.0", "High"), ("Rhodplumsite", "2", "10.002", "20.0", "High"),
         ("Iridium", "3", "10.0", "20.002", "High"), ("Iridium", "6", "10.2", "20.0", "High"),
         ("Iridium", "4", "10.001", "20.001", "Depleted")]
for commodity, rigs, lat, lon, amount in spots:
    store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity=commodity, rigs=rigs,
                      density="High", amount=amount, lat=lat, lon=lon)
store.add_deposit(system="Ega", body="Ega A 1", location="2", commodity="Gold", rigs="2",
                  density="Low", amount="Low", lat="-5.0", lon="40.0")
inputs = ST.picture_inputs(store, "Ega", "Ega A 1", "1")
check("a picture of a site is drawn from its body's deposits, measured from where it was logged",
      inputs is not None and inputs["signal"] == "1" and inputs["anchor"] == (0.0, 0.0)
      and len(inputs["rows"]) == 6 and inputs["rows"][0]["range_m"] == 0.0, inputs and len(inputs["rows"]))
scene = MI.build_scene(inputs["rows"], system="Ega", body="Ega A 1", signal=inputs["signal"],
                       anchor=inputs["anchor"], when=1700000000, version="1.10042")
check("every deposit of the site is on it", len(scene["markers"]) == 5, len(scene["markers"]))
check("each carries its position", all(m["position"] for m in scene["markers"])
      and sorted(m["position"] for m in scene["markers"])[0] == (10.0, 20.0))
check("and its row gives it, to four places", "Rhodplumsite  10.0020, 20.0000" in scene["texts"], scene["texts"])
check("a position reads the same south and west", MI.position_text((-5.25, -120.5)) == "-5.2500, -120.5000"
      and MI.position_text(None) == "")
tops = scene["top_patches"]
check("the top patches are circled: the knot of nine rigs, then the six on its own",
      [(p["n"], p["rigs"], p["count"]) for p in tops] == [(1, 9, 3), (2, 6, 1)], tops)
check("each circle is as wide as a top patch on the map", all(p["r"] > 0 for p in tops)
      and len({round(p["r"], 3) for p in tops}) == 1, tops)
check("and named in the picture's words", "TOP PATCH 1  9R  3 finds" in scene["texts"], scene["texts"])
narrow = MI.build_scene(inputs["rows"], signal="1", anchor=(0.0, 0.0), golden_m=500)
check("the circles follow the map's own patch width", narrow["top_patches"][0]["r"] < tops[0]["r"],
      (narrow["top_patches"][0]["r"], tops[0]["r"]))
check("what the picture already said is still said", any(t.startswith("BEST PATCH") for t in scene["texts"])
      and "Ega / Ega A 1   signal 1" in scene["texts"] and any("5 deposits" in t for t in scene["texts"]),
      scene["texts"])
ok, why = MI.pillow_status()
if ok:
    image = MI.draw_scene(scene)
    check("it is drawn, at the size it always was", image.size == MI.SIZE, image.size)

    def gold_pixels(picture):
        raw = picture.convert("RGB").tobytes()
        return sum(1 for i in range(0, len(raw), 3)
                   if raw[i] > 200 and 170 < raw[i + 1] < 225 and raw[i + 2] < 120)
    gold = gold_pixels(image)
    less = gold_pixels(MI.draw_scene(dict(scene, top_patches=[])))
    check("with the top patches' circles on it, in gold", gold > less, (gold, less))
else:
    print("  SKIP  drawing it   (%s)" % why)
empty = MI.build_scene([], system="Ega", body="Ega A 1")
check("a picture of nothing has no patches and is not an error", empty["top_patches"] == [])

print("== C14: a picture of any site, and of each surveyed area ==")
check("a site with no position anywhere has no picture to draw",
      ST.picture_inputs(store, "Ega", "No such body", "1") is None)
loose = SV.Survey(os.path.join(TMP, "loose"))
loose.add_deposit(system="Ega", body="Ega C 2", location="7", commodity="Gold", rigs="2",
                  amount="Low", lat="3.0", lon="3.0")
check("nor one whose body's size is not known", ST.picture_inputs(loose, "Ega", "Ega C 2", "7") is None)
cmap = CV.CoverageMap("Ega", "Ega A 1", R)
cmap.signal = "1"
for step in range(12):
    cmap.add_fix(10.0, 20.0 + step * 0.002)
cmap.set_centre(10.0, 20.0)
cmap.set_border(10.0, 20.03)
bare = CV.CoverageMap("Ega", "Ega A 1", R)
rows = ST.areas([cmap, bare])
check("one row a surveyed area with ground swept in it; an empty one is no row",
      len(rows) == 1 and rows[0]["n"] == 1 and rows[0]["signal"] == "1" and rows[0]["map"] is cmap, rows)
check("how much was swept, and how much of its border", rows[0]["km2"] > 0 and rows[0]["percent"] is not None,
      rows[0])
line = ST.area_line(rows[0])
check("as a line", line.startswith("Area 1 - location 1 - ") and "km2 swept" in line and "% of its border" in line,
      line)
area = ST.picture_inputs(store, "Ega", "Ega A 1", area=cmap)
check("an area's picture is measured from its own centre, with the ground swept",
      area is not None and area["signal"] == "1" and area["survey"]["border_m"] == cmap.border_m
      and area["survey"]["centre"] == (0.0, 0.0) and len(area["survey"]["points"]) == len(cmap.points)
      and area["survey"]["percent"] == rows[0]["percent"], area and area["survey"].keys())
scene = MI.build_scene(area["rows"], system="Ega", body="Ega A 1", signal=area["signal"],
                       anchor=area["anchor"], survey=area["survey"])
check("and draws with its border and swept ground", scene["border"] is not None and scene["swept"]
      and any("swept" in t for t in scene["texts"]), scene["texts"])
check("no maps, no rows", ST.areas([]) == [] and ST.areas(None) == [])

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
