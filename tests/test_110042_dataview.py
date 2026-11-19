"""1.10042: My sites becomes the one data window.

  - the systems with their counts and the totals over the list (C1);
  - beside the list, systems that open into their bodies grouped by ground
    (C2) and bodies that open into their locations, each a line with how far
    it is from you (C3), and the surveyed areas of a body, each with a
    picture (C14);
  - a location picked there lists its deposits: top patch first, worked out
    last with what it gave (C4, C11, C13);
  - the deposit card beside them: everything about it, and Guide me there,
    Share, Mark depleted, Copy position, Delete (C5);
  - the location's map picture beside the card (C6);
  - one material filter the whole window follows (C7);
  - Import on the top row (C8);
  - a key that brings the window up (C9);
  - guiding to a deposit on any body, kept until you get there, with Stop
    guiding (C10);
  - your own good and bad marks on any logged location (C12);
  - "Worth mining only" in the materials picker (C15);
  - the saved map picture circles the top patches at the map's own width
    (C16).

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_dataview.py
"""
import faulthandler
import json
import os
import sys
import tempfile
import time

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-dataview-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import edsmt as A           # noqa: E402
import farguide as FG       # noqa: E402
import ownmarks as OM       # noqa: E402
import inputdev as IND      # noqa: E402
import mapimage as MI       # noqa: E402
import coverage as CV       # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION, "find_unlocked": True}, handle)
A._windows_clipboard = lambda *args, **kwargs: False
opened_paths = []
A.open_path = lambda path: opened_paths.append(path)
answers = []
A.confirm = lambda window, title, text: answers.pop(0) if answers else False

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


app = A.EDSMT()
app.geometry("1500x950+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(seconds=0.2):
    until = time.time() + seconds
    while True:
        app.update_idletasks()
        app.update()
        if time.time() >= until:
            break
        time.sleep(0.01)


def settle_until(cond, seconds=5.0):
    until = time.time() + seconds
    while time.time() < until:
        if cond():
            return True
        pump(0.05)
    return bool(cond())


pump()
R = 1_000_000.0
store = app.store
store.set_location("Ega", "Ega A 1", "1", lat=10.0, lon=20.0, radius_m=R,
                   commodities=["Iridium", "Rhodplumsite"])
store.set_location("Ega", "Ega A 1", "2", lat=-5.0, lon=40.0, radius_m=R, commodities=["Gold"])
store.set_location("Ega", "Ega B 3", "4", lat=1.0, lon=1.0, radius_m=R, commodities=["Gold"])
north = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Iridium",
                          rigs="4", density="High", amount="High", lat="10.01", lon="20.0",
                          mined="Iridium:120;Gold:9", recorded="2026-11-01T10:00:00Z")
east = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Rhodplumsite",
                         rigs="6", density="Low", amount="Medium", lat="10.0", lon="20.05",
                         recorded="2026-11-02T10:00:00Z")
spent = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Iridium",
                          rigs="4", density="High", amount="Depleted", lat="10.0", lon="20.0",
                          cycles="2026-10-01=300;2026-10-20=340", recorded="2026-10-20T10:00:00Z")
gold = store.add_deposit(system="Ega", body="Ega A 1", location="2", commodity="Gold",
                         rigs="3", density="Medium", amount="High", lat="-5.0", lon="40.0",
                         recorded="2026-11-03T10:00:00Z")
far = store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5", commodity="Haematite",
                        rigs="2", density="Medium", amount="Low", lat="1.0", lon="1.0",
                        recorded="2026-09-20T10:00:00Z")
blind = store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5", commodity="Haematite",
                          rigs="1", density="Low", amount="Low", lat="", lon="",
                          recorded="2026-09-21T10:00:00Z")

app.here = lambda: ("Ega", "Ega A 1")
shown_tabs = []
app.show_map = lambda: shown_tabs.append("map")
win = app.open_sites()
win = app.docked_tools.get("sites") or win
win.refresh()
pump()

print("== C1: the systems, with their counts and totals ==")
summary = win.summary.cget("text")
check("the totals over the list: systems, locations, deposits, rigs, tonnes mined",
      "2 systems - 4 locations - 6 deposits" in summary and "760t mined" in summary, summary)
places = win.places
settle_until(lambda: places.row_count() >= 2)
kinds = [places.payload(i)["kind"] for i in range(places.row_count())]
check("the places list starts with a row a system", kinds.count("system") == 2, kinds)
row0 = next(places.payload(i) for i in range(places.row_count()) if places.payload(i)["kind"] == "system"
            and places.payload(i)["system"] == "Ega")
check("each with its counts", "3 locations" in places.cell_text(
    [places.payload(i) for i in range(places.row_count())].index(row0), 0)[1]
    or "3 locations" in places.cell_text([places.payload(i) for i in range(places.row_count())].index(row0), 0)[0],
    places.cell_text([places.payload(i) for i in range(places.row_count())].index(row0), 0))


def index_of(pred):
    for i in range(places.row_count()):
        if pred(places.payload(i)):
            return i
    return -1


print("== C2, C3: a system opens into its bodies by ground, a body into its locations ==")
app.ground_of = lambda system, body: ("Metal rich body", "") if body == "Ega A 1" else None
win.open_place(row0)
kinds = [(places.payload(i)["kind"], places.payload(i).get("body") or places.payload(i).get("ground")
          or places.payload(i).get("system")) for i in range(places.row_count())]
check("the system's bodies, under a heading for their ground",
      ("ground", "Metal rich body") in kinds and ("body", "Ega A 1") in kinds and ("body", "Ega B 3") in kinds,
      kinds)
body_row = places.payload(index_of(lambda r: r["kind"] == "body" and r["body"] == "Ega A 1"))
app.where_you_are = lambda: {"system": "Ega", "body": "Ega A 1", "lat": 10.0, "lon": 20.01,
                             "radius_m": R, "heading": 0.0}
win.open_place(body_row)
at = index_of(lambda r: r["kind"] == "location" and r["body"] == "Ega A 1" and r["location"] == "1")
check("the body opens into its locations", at >= 0, [places.payload(i)["kind"] for i in range(places.row_count())])
text = places.cell_text(at, 0)[0]
check("each a line saying what is there", "Location 1 - 3 deposits" in text, text)
check("and how far it is from you", "from you" in places.cell_text(at, 3)[0], places.cell_text(at, 3))
win.open_place(places.payload(at))
check("a location opened shows its deposits under it",
      places.payload(at + 1) is not None and places.payload(at + 1)["kind"] == "deposit")
win.open_place(places.payload(at))
check("and folds again", places.payload(at + 1) is None or places.payload(at + 1)["kind"] != "deposit")

print("== C4, C11, C13: the location's deposits ==")
win.show_place("Ega", "Ega A 1", "1")
pump()
table = win.deposits
rows = [table.payload(i) for i in range(table.row_count())]
order = [row["id"] for row in rows]
expected = [r["id"] for r in A.STR.deposits(store, "Ega", "Ega A 1", "1", radius_m=app.golden_radius())]
check("top patch first, as the map has it, worked out last", order == expected and order[-1] == spent["id"]
      and rows[0]["patch"] == 1, [(r["commodity"], r["rigs"], r["patch"]) for r in rows])
col = {name: index for index, name in enumerate(A.DEPOSIT_HEADERS)}
check("a worked-out deposit says what it gave last time",
      table.cell_text(order.index(spent["id"]), col["Est. left"])[0] == "worked out (340t)",
      table.cell_text(order.index(spent["id"]), col["Est. left"]))
check("rigs, from centre, mined and est. left are its columns",
      all(name in A.DEPOSIT_HEADERS for name in ("Rigs", "From centre", "Mined", "Est. left")))
check("and edit is one of its buttons", "edit" in [t for t, _c, _p in table.actions_for(0)])

print("== C5: the deposit card ==")
table.pick(order.index(north["id"]))
pump()
card = win.card_text.cget("text")
check("the card follows the deposit picked", win.card_title.cget("text") == "Iridium - location 1",
      win.card_title.cget("text"))
check("its coordinates", "10.010000, 20.000000" in card, card)
check("heading and distance from you", "From you" in card and " m " in card.split("From you")[1].splitlines()[0]
      or "km" in card.split("From you")[1].splitlines()[0], card)
check("amount, density, mined, left, price, marked, state",
      all(word in card for word in ("Amount", "Density", "Mined this time", "Left", "Price", "Marked", "State")),
      card)
names = [b.cget("text") for b in win.card_buttons]
check("its buttons", names == ["Guide me there", "Share", "Mark depleted", "Copy position", "Delete"], names)
copied = []
app.clipboard_clear = lambda: None
app.clipboard_append = lambda text: copied.append(text)
win.clipboard_clear = lambda: None
win.clipboard_append = lambda text: copied.append(text)
win.card_action("Copy position")
check("Copy position is the position", copied and copied[-1] == "10.01, 20.0", copied[-1:])
win.card_action("Share")
check("Share is the line another EDSMT takes", copied and copied[-1] == A.share_line(north), copied[-1:])
win.card_action("Mark depleted")
pump()
check("Mark depleted marks it worked out", A.SV.is_depleted(next(
    d for d in store.deposits if d["id"] == north["id"]).get("amount")))
answers.append(False)
win.show_place("Ega", "Ega A 1", "2")
pump()
table.pick(0)
pump()
win.card_action("Delete")
check("Delete asks first; no is no", any(d["id"] == gold["id"] for d in store.deposits))
answers.append(True)
win.card_action("Delete")
pump()
check("yes deletes it", not any(d["id"] == gold["id"] for d in store.deposits))

print("== C10: guide me there, to any deposit on any body ==")
app._guide_to = None
win.show_place("HR 7280", "HR 7280 A 3", "5")
pump()
table.pick([table.payload(i)["id"] for i in range(table.row_count())].index(far["id"]))
pump()
win.card_action("Guide me there")
target = FG.from_settings(app.settings.get(FG.SETTING))
check("a deposit in another system is kept as the target", target is not None and target["id"] == far["id"],
      app.settings.get(FG.SETTING))
check("and the overlay is told which one", str(app._guide_to) == str(far["id"]))
check("the window says in plain words what to do", "Jump there and land on" in win.guide_line.cget("text"),
      win.guide_line.cget("text"))
check("with Stop guiding beside it", win.stop_button.winfo_manager() != "")
win.stop_guiding()
check("Stop guiding lets it go", app.settings.get(FG.SETTING) is None and app._guide_to is None
      and "Guide me there" in win.guide_line.cget("text"), (app.settings.get(FG.SETTING), app._guide_to))
table.pick([table.payload(i)["id"] for i in range(table.row_count())].index(blind["id"]))
pump()
win.card_action("Guide me there")
check("no position: says why there is no guidance", "No position was recorded" in win.guide_line.cget("text")
      and app.settings.get(FG.SETTING) is None, win.guide_line.cget("text"))
app.settings[FG.SETTING] = FG.to_settings(FG.target_of(far))
app._guide_to = None
app.restore_far_guide()
check("the target is kept across a restart", str(app._guide_to) == str(far["id"]))
app.far_arrived(far["id"])
check("and let go once you get there", app.settings.get(FG.SETTING) is None)

print("== C7: one material filter the whole window follows ==")
win.commodity.set("Rhodplumsite")
win._paint()
win.show_place("Ega", "Ega A 1", "1")
pump()
check("the deposits follow it", {table.payload(i)["commodity"] for i in range(table.row_count())}
      == {"Rhodplumsite"})
check("the totals follow it", "1 deposit" in win.summary.cget("text"), win.summary.cget("text"))
sys_rows = [places.payload(i) for i in range(places.row_count()) if places.payload(i)["kind"] == "system"]
check("and the places list", [r["system"] for r in sys_rows] == ["Ega"], sys_rows)
win.commodity.set("Any")
win._paint()

print("== C8: Import in sight ==")
check("Import is on the top row, beside Refresh", win.import_button.master is win.refresh_button.master
      and win.import_button.winfo_manager() == "pack")

print("== C9: a key brings the window up ==")
check("there is a key for it, unbound until picked", A.DEFAULT_SETTINGS.get("hotkey_sites") == ""
      and "sites" in IND.JOY_ACTIONS and "hotkey_sites" in A.SETTING_TIPS)
check("bound, it is registered", A.EDSMT.wanted_hotkeys(dict(A.DEFAULT_SETTINGS, hotkey_sites="ALT+M"))
      .get("sites") == "ALT+M")
called = []
real_open = app.open_sites
app.open_sites = lambda: called.append(1) or real_open()
app.show_sites_key()
app.open_sites = real_open
check("pressed, it opens the window", called == [1])

print("== C12: your own marks ==")
win.commodity.set("Any")
win._paint()
site_index = {(win.table.payload(i)["body"], win.table.payload(i)["signal"]): i
              for i in range(win.table.row_count())}
b3 = site_index[("Ega B 3", "4")]
buttons = {t: c for t, c, _p in win.table.actions_for(b3)}
check("every logged location has the two marks", OM.LABELS[OM.UP] in buttons and OM.LABELS[OM.DOWN] in buttons,
      list(buttons))
buttons[OM.LABELS[OM.UP]]()
pump()
check("marked up, it is kept", app.own_marks().mine("Ega", "Ega B 3", "4") == OM.UP)
check("and sorts to the top", win.table.payload(0)["body"] == "Ega B 3",
      [win.table.payload(i)["body"] for i in range(win.table.row_count())])
check("and is coloured", win.table.row_tone(0) == "good", win.table.row_tone(0))
ix = [i for i in range(win.table.row_count()) if win.table.payload(i)["body"] == "HR 7280 A 3"][0]
{t: c for t, c, _p in win.table.actions_for(ix)}[OM.LABELS[OM.DOWN]]()
pump()
check("marked down, it goes last", win.table.payload(win.table.row_count() - 1)["body"] == "HR 7280 A 3")
check("and is toned bad", win.table.row_tone(win.table.row_count() - 1) == "bad")
check("kept on this PC", os.path.isfile(os.path.join(A.DATA_DIR, OM.FILE_NAME)))
b3 = [i for i in range(win.table.row_count()) if win.table.payload(i)["body"] == "Ega B 3"][0]
{t: c for t, c, _p in win.table.actions_for(b3)}[OM.LABELS[OM.UP]]()
check("pressed again, the mark comes off", app.own_marks().mine("Ega", "Ega B 3", "4") == "")

print("== C14, C6: pictures ==")
ok, why = MI.pillow_status()
ix = [i for i in range(win.table.row_count()) if win.table.payload(i)["body"] == "Ega A 1"
      and win.table.payload(i)["signal"] == "1"][0]
names = [t for t, _c, _p in win.table.actions_for(ix)]
check("every site has a map picture button", "map picture" in names, names)
cmap = app.survey_book.map_for("Ega", "Ega A 1", 10.0, 20.0, R)
cmap.signal = "1"
for step in range(12):
    cmap.add_fix(10.0, 20.0 + step * 0.002)
cmap.set_centre(10.0, 20.0)
cmap.set_border(10.0, 20.03)
win.open_place(dict(row0)) if index_of(lambda r: r["kind"] == "body") < 0 else None
win.refresh_places()
at = index_of(lambda r: r["kind"] == "area" and r["body"] == "Ega A 1")
check("an opened body lists its surveyed areas", at >= 0,
      [(places.payload(i)["kind"], places.payload(i).get("body")) for i in range(places.row_count())])
if at >= 0:
    check("each with a picture button", "picture" in [t for t, _c, _p in places.actions_for(at)])
if ok:
    before = len(opened_paths)
    {t: c for t, c, _p in win.table.actions_for(ix)}["map picture"]()
    check("a site's picture is saved and opened", len(opened_paths) == before + 1
          and opened_paths[-1].endswith(".png") and os.path.isfile(opened_paths[-1]), opened_paths[-1:])
    if at >= 0:
        {t: c for t, c, _p in places.actions_for(at)}["picture"]()
        check("and an area's", len(opened_paths) == before + 2, opened_paths[-1:])
    win.show_place("Ega", "Ega A 1", "1")
    settle_until(lambda: win.map_view.cget("text") == "")
    check("the location's map is shown beside the card", win.map_view.cget("text") == ""
          and win.map_view.cget("image") not in ("", None), win.map_view.cget("text"))
else:
    print("  SKIP  pictures   (%s)" % why)
win.show_place("Ega", "No such body", "9")
pump()
check("a location with nothing to draw says so in the map's place", win.map_view.cget("text") != "")

print("== C15: worth mining only ==")
picker = A.MaterialsWindow(app)
pump()
picker.tick_worth()
ticked = sorted(name for name, var in picker.ticks.items() if var.get())
check("ticks only the materials worth a trip", ticked == sorted(A.MT.worth_mining(list(picker.ticks),
                                                                                 app.market_prices())),
      ticked)
check("and that is fewer than all", 0 < len(ticked) < len(picker.ticks), len(ticked))
picker.destroy()

print("== C16: the saved picture circles the top patches at the map's own width ==")
seen = {}
real_render = A.MI.render_map


def spy(rows, **kwargs):
    seen.update(kwargs)
    return real_render(rows, **kwargs)


A.MI.render_map = spy
app.settings["golden_radius_m"] = 1500
app.plan_inputs = lambda: {"rows": [north, east], "system": "Ega", "body": "Ega A 1", "signal": "1",
                           "anchor": (0.0, 0.0), "survey": None, "rigs": None, "trail": None}
app.picture_now(save=False)
A.MI.render_map = real_render
check("the map's patch width goes to the picture", seen.get("golden_m") == app.golden_radius(), seen.keys())

print("== nothing logged ==")
store.deposits[:] = []
store.locations[:] = []
win.refresh()
pump()
check("an empty record is no error", places.row_count() == 0 and win.card_title.cget("text") == "")

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
