"""1.10042: My sites shows the deposits of the site you pick.

Everything about a deposit was recorded and a commander had to go looking
for it: the tonnes mined and what is left were only in the details of a
deposit picked on the map, on the body you were standing on. My sites now
lists the picked site's deposits under the list: rigs, where each is from
the location's centre, mined, estimated left, and the buttons to act on it.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_datawindow.py
"""
import faulthandler
import json
import os
import sys
import tempfile
import time

faulthandler.dump_traceback_later(240, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-datawindow-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import edsmt as A     # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION, "find_unlocked": True}, handle)
# Copies take the Tk path everywhere, and never touch the real clipboard.
A._windows_clipboard = lambda *args, **kwargs: False

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


app = A.EDSMT()
app.geometry("1400x900+0+0")
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
    """Wait for `cond`, up to a deadline - never a fixed number of loops."""
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
north = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Iridium",
                          rigs="4", density="High", amount="High", lat="10.01", lon="20.0",
                          mined="Iridium:120;Gold:9", recorded="2026-11-01T10:00:00Z")
east = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Rhodplumsite",
                         rigs="6", density="Low", amount="Medium", lat="10.0", lon="20.05",
                         recorded="2026-11-02T10:00:00Z")
spent = store.add_deposit(system="Ega", body="Ega A 1", location="1", commodity="Iridium",
                          rigs="4", density="High", amount="Depleted", lat="10.0", lon="20.0",
                          cycles="2026-10-01=300;2026-10-20=340", recorded="2026-10-20T10:00:00Z")
far = store.add_deposit(system="HR 7280", body="HR 7280 A 3", location="5", commodity="Haematite",
                        rigs="2", density="Medium", amount="Low", lat="1.0", lon="1.0",
                        recorded="2026-09-20T10:00:00Z")

app.here = lambda: ("Ega", "Ega A 1")
edited, guided, shown_tabs = [], [], []
app.edit_deposit = lambda deposit: edited.append(deposit)
app.pick_deposit = lambda deposit, guide=True: guided.append(deposit)
app.show_map = lambda: shown_tabs.append("map")
win = app.open_sites()
win = app.docked_tools.get("sites") or win
win.refresh()
table = win.deposits
settle_until(lambda: table.row_count() == 3)

print("== the picked site's deposits, under the list ==")
check("the list still opens with every site", len(win._rows) == 2, len(win._rows))
check("the site you are on is first, and picked", win.table.focus_row()["body"] == "Ega A 1")
check("its deposits are listed without a click", table.row_count() == 3, table.row_count())
check("under a heading that says which site", "Ega A 1" in win.detail_title.cget("text")
      and "location 1" in win.detail_title.cget("text"), win.detail_title.cget("text"))
check("and how much is there", "3 deposits" in win.detail_title.cget("text")
      and "10 rigs" in win.detail_title.cget("text"), win.detail_title.cget("text"))
check("the headings a commander looks for", list(A.DEPOSIT_HEADERS) ==
      ["Commodity", "Rigs", "From centre", "Mined", "Est. left", "Amount", "Density", "Marked"])
col = {name: index for index, name in enumerate(A.DEPOSIT_HEADERS)}
rows = [table.payload(i) for i in range(table.row_count())]
at = {row["id"]: index for index, row in enumerate(rows)}
n, e, s = at[north["id"]], at[east["id"]], at[spent["id"]]
# C11 (1.10042) changed the order on purpose: no longer nearest the centre
# first, but the map's own top patches first, in the map's order, and the
# worked-out one last.
expected = [r["id"] for r in A.STR.deposits(store, "Ega", "Ega A 1", "1", radius_m=app.golden_radius())]
check("top patch first as the map ranks them, worked out last",
      [row["id"] for row in rows] == expected and s == 2 and rows[0]["patch"] == 1, (s, n, e))
check("where it is from the location's centre", table.cell_text(n, col["From centre"])[0] == "175 m N 000",
      table.cell_text(n, col["From centre"]))
check("the one on the centre says so", table.cell_text(s, col["From centre"])[0] == "at the centre")
check("rigs", table.cell_text(e, col["Rigs"])[0] == "6", table.cell_text(e, col["Rigs"]))
check("tonnes mined from it", table.cell_text(n, col["Mined"])[0] == "120t", table.cell_text(n, col["Mined"]))
check("with the by-products in the whole text, not added in",
      "Gold 9t" in table.cell_text(n, col["Mined"])[1], table.cell_text(n, col["Mined"]))
check("nothing mined is a dash", table.cell_text(e, col["Mined"])[0] == "-")
check("what is thought to be left", table.cell_text(n, col["Est. left"])[0] == "est. 180-220t",
      table.cell_text(n, col["Est. left"]))
check("and what that rests on, in the whole text",
      "2 times a deposit of yours with 4 rigs and High density" in table.cell_text(n, col["Est. left"])[1],
      table.cell_text(n, col["Est. left"]))
# 1.10042 (D1): nothing measured is said in words, not a dash - still no guess.
check("not known is 'not measured yet', not a guess",
      table.cell_text(e, col["Est. left"])[0] == "not measured yet")
check("a worked-out deposit says so, with what it gave last time (C13)",
      table.cell_text(s, col["Est. left"])[0] == "worked out (340t)"
      and table.cell_text(s, col["Amount"])[0] == "Depleted")
check("and is toned as one", table.row_tone(s) == "bad", table.row_tone(s))

print("== it follows the list ==")
other = next(i for i in range(win.table.row_count()) if win.table.payload(i)["body"] == "HR 7280 A 3")
win.table.pick(other)
check("pick another site and its deposits are shown", table.row_count() == 1
      and table.payload(0)["id"] == far["id"], table.row_count())
check("the heading follows", "HR 7280 A 3" in win.detail_title.cget("text"), win.detail_title.cget("text"))
check("a location never logged has no centre to measure from",
      table.cell_text(0, col["From centre"])[0] == "-", table.cell_text(0, col["From centre"]))
win.table.pick(next(i for i in range(win.table.row_count()) if win.table.payload(i)["body"] == "Ega A 1"))

print("== it follows the commodity filter ==")
win.commodity.set("Rhodplumsite")
win._paint()
check("one commodity picked: only its deposits", [table.payload(i)["commodity"] for i in
      range(table.row_count())] == ["Rhodplumsite"], table.row_count())
check("and the heading says they are some of them", "1 of 3 deposits" in win.detail_title.cget("text"),
      win.detail_title.cget("text"))
win.commodity.set("Any")
win._paint()
check("Any brings them back", table.row_count() == 3, table.row_count())

print("== what can be done with one ==")
names = [text for text, _command, _primary in table.actions_for(n)]
check("edit, copy to share, copy position - and guide, on the body you are on",
      names == ["guide me there", "edit", "copy to share", "copy position"], names)
copied = []
win.clipboard_clear = lambda: None
win.clipboard_append = lambda text: copied.append(text)
app.clipboard_clear = lambda: None
app.clipboard_append = lambda text: copied.append(text)
run = {text: command for text, command, _primary in table.actions_for(n)}
run["edit"]()
check("edit opens the editor on that deposit", edited == [north], edited)
run["copy position"]()
check("copy position is the latitude and longitude", copied[-1] == "10.01, 20.0", copied[-1:])
run["copy to share"]()
check("copy to share is the line another EDSMT takes", copied[-1] == A.share_line(north), copied[-1:])
run["guide me there"]()
check("guide me there picks it on the map, and shows the map", guided == [north] and shown_tabs == ["map"],
      (guided, shown_tabs))
win.table.pick(other)
names = [text for text, _command, _primary in table.actions_for(0)]
# C10 (1.10042): guiding is offered to a deposit on any body now, kept until
# you get there; the map is not shown for a body you are not on.
check("on another body guiding is offered too", "guide me there" in names and "edit" in names, names)
guided[:] = []
dict((t, c) for t, c, _p in table.actions_for(0))["guide me there"]()
check("and keeps it as the target, without picking it on this body's map",
      guided == [] and str(app._guide_to) == str(far["id"]), (guided, app._guide_to))
app.stop_far_guide()

print("== the bin has no deposits to show ==")
win.toggle_bin()
check("in the bin the deposits are put away", table.row_count() == 0
      and win.detail_title.cget("text") == "", (table.row_count(), win.detail_title.cget("text")))
win.toggle_bin()
check("and back with the list", table.row_count() >= 1, table.row_count())

print("== nothing logged ==")
store.deposits[:] = []
store.locations[:] = []
win.refresh()
pump()
check("with nothing logged there is nothing under the list, and no error",
      table.row_count() == 0 and win.detail_title.cget("text") == "",
      (table.row_count(), win.detail_title.cget("text")))

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
