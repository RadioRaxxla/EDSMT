"""1.10042: tonnes left for everyone (D1, D2, D4).

A deposit worked out sends the tonnes it gave. The community map answers a
range of tonnes for a commodity, rig count and Density once five alike have
been worked out. A deposit shows YOUR own figure first when you have worked
it out before, otherwise the community range with how many reports are behind
it, otherwise "not measured yet" - in the deposits table, the card of My
sites and the details of the main window. Before a deposit is worked out it
shows tonnes held and left from the same ranges and what has been refined
there so far. Deposits worked out before this version are sent once.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_tonnesleft.py
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
TMP = tempfile.mkdtemp(prefix="edsmt-tonnes42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import tonnesleft as TL   # noqa: E402
import sitetree as STR    # noqa: E402
import crowd as CR        # noqa: E402
import edonline as EDO    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=6)
        return fn
    return wrap


GROUPS = {"groups": [
    {"commodity": "Platinum", "rigs": 4, "density": "High", "samples": 9, "measured": True,
     "low": 110, "high": 140},
    {"commodity": "Gold", "rigs": 3, "density": "Low", "samples": 2, "measured": False,
     "low": None, "high": None}], "least": 5}


@section("the book of ranges")
def _book():
    book = TL.TonnesBook()
    check("empty, it knows nothing", book.range_for("Platinum", 4, "High") is None)
    check("it takes the server's list", book.take(GROUPS) is True)
    check("and answers a range with how many reports are behind it",
          book.range_for("Platinum", 4, "High") == (110, 140, 9), book.range_for("Platinum", 4, "High"))
    check("whatever the case or spelling", book.range_for("platinum", "4", "high") == (110, 140, 9))
    check("another rig count is another group", book.range_for("Platinum", 5, "High") is None)
    check("a group below five is no range", book.range_for("Gold", 3, "Low") is None)
    check("rubbish is not taken", book.take({"nothing": 1}) is False and book.take(None) is False)
    check("a single answer is taken too", book.take({"commodity": "Gold", "rigs": 3, "density": "Low",
          "samples": 6, "measured": True, "low": 20, "high": 30}) and
          book.range_for("Gold", 3, "Low") == (20, 30, 6))
    check("the crowd keeps one", isinstance(CR.Crowd().tonnes, TL.TonnesBook))
    crowd = CR.Crowd()
    check("and takes it by its tag", crowd.take(CR.TONNES_TAG, GROUPS) and
          crowd.tonnes.range_for("Platinum", 4, "High") is not None)


def live(**extra):
    row = {"id": "x", "system": "Ega", "body": "Ega 1", "location": "1", "commodity": "Platinum",
           "rigs": "4", "density": "High", "amount": "High", "mined": "", "cycles": "",
           "notes": "", "lat": "10.0", "lon": "20.0"}
    row.update(extra)
    return row


@section("which figure is shown: your own, then the range, then none")
def _figure():
    book = TL.TonnesBook()
    book.take(GROUPS)
    mine = live(cycles="2026-10-01=120;2026-10-20=130")
    held = STR.holds(mine, [], book)
    check("worked out before: your own, first", held and held[3] == STR.MEASURED and held[:2] == (120, 130), held)
    held = STR.holds(live(), [], book)
    check("not before: the range", held and held[3] == STR.CROWD and held[:3] == (110, 140, 9), held)
    check("and it is said as an estimate with the reports behind it",
          STR.left_text(held).startswith("est. 110-140t"), STR.left_text(held))
    check("the basis names how many reports", "9 reports" in STR.left_basis(held, live()),
          STR.left_basis(held, live()))
    other = live(commodity="Bauxite")
    check("nothing alike: no figure", STR.holds(other, [], book) is None)
    check("and the table says not measured yet", STR.left_text(None) == "not measured yet", STR.left_text(None))
    check("a worked-out deposit is not 'not measured yet'", STR.left_text(None, True) == "worked out")


@section("D2: held and left before it is worked out, from the range and what has been refined")
def _left():
    book = TL.TonnesBook()
    book.take(GROUPS)
    got = STR.left(live(mined="Platinum:30;Gold:4"), [], book)
    check("left is the range less what has been refined here", got and got[:2] == (80, 110), got)
    check("and it is a community estimate", got and got[3] == STR.CROWD, got)
    check("a worked-out deposit has none", STR.left(live(amount="Depleted"), [], book) is None)


@section("D4: tonnes of deposits already worked out are found for one catch-up send")
def _catchup():
    rows = TL.catchup([live(id="a", cycles="2026-09-20=56;2026-10-02=48"),
                       live(id="b", cycles=""), live(id="c", cycles="2026-10-05=0;junk;2026-10-06=77")])
    got = sorted((d["id"], t, day) for d, t, day in rows)
    check("each worked-out cycle once, with its day, nothing for the rest",
          got == [("a", 48, "2026-10-02"), ("a", 56, "2026-09-20"), ("c", 77, "2026-10-06")], got)
    check("none to send is an empty list", TL.catchup([live()]) == [] and TL.catchup(None) == [])


@section("the community client may be asked for tonnes")
def _client():
    check("the tag is its own", CR.TONNES_TAG == "tonnes")
    client = EDO.CommunityClient(EDO.Worker())
    seen = []
    client.worker.submit = lambda tag, fn: seen.append(tag)
    client.configure("", "", True, True)
    check("it asks", client.crowd("tonnes", tag=CR.TONNES_TAG) is True and seen == [CR.TONNES_TAG], seen)
    check("a report carries tonnes, and a day only for a catch-up",
          TL.report_fields(96) == {"tonnes": 96} and
          TL.report_fields(48, "2026-10-02") == {"tonnes": 48, "tonnes_on": "2026-10-02"} and
          TL.report_fields(0) == {} and TL.report_fields(None) == {} and TL.report_fields("x") == {})


# ---------------------------------------------------------------------------
HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the toolkit half of this file - no display (%s)." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


class FakeCommunity:
    ready = can_read = True

    def __init__(self):
        self.asked, self.uploads = [], []

    def crowd(self, what, tag=""):
        self.asked.append((what, tag))
        return True

    def upload(self, cmdr, rows):
        self.uploads.append((cmdr, rows))
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: True


if HAVE_DISPLAY:
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION, "journal_dir": JOURNALS,
                   "tour_done": True}, _f)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()


@on_screen("MINED OUT sends the tonnes the deposit gave")
def _mined():
    fake = app.community = FakeCommunity()
    app.watcher.cmdr = "CMDR Cee"
    app.store.set_location("Ega", "Ega 1", "1", lat=10.0, lon=20.0, radius_m=1500000.0)
    row = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Platinum", rigs="4",
                                density="High", amount="High", lat="10.01", lon="20.0",
                                mined="Platinum:96;Gold:5")
    app.selected = row
    app.mark_mined()
    sent = [r for _c, rows in fake.uploads for r in rows]
    check("one report went up", len(sent) == 1, fake.uploads)
    check("it carries the tonnes of its own commodity, not the by-products",
          sent and sent[0].get("tonnes") == 96 and sent[0].get("amount") == "Depleted", sent)
    check("no catch-up day on a live report", sent and not sent[0].get("tonnes_on"), sent)
    fake.uploads.clear()
    app.mark_mined()
    check("a second MINED OUT with nothing refined sends no tonnes",
          all(not r.get("tonnes") for _c, rows in fake.uploads for r in rows), fake.uploads)


@on_screen("the details and the table show the range and 'not measured yet'")
def _shown():
    app.community = FakeCommunity()
    app.crowd_figures().take(CR.TONNES_TAG, GROUPS)
    store = app.store
    row = store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Platinum", rigs="4",
                            density="High", amount="High", lat="10.02", lon="20.0", mined="Platinum:20")
    app.on_pick(row)
    pump()
    card = app.detail.cget("text")
    lines = "\n".join(A.tonnes_lines(row, store.deposits, app.crowd_figures().tonnes))
    check("the lines say what it holds, what is left and how many reports", "est. holds 110-140t" in lines
          and "est. left: 90-120t" in lines and "9 reports" in lines, lines)
    check("the main details say what it holds and what is left", "est. holds 110-140t" in card
          and "est. left: 90-120t" in card, card)
    bare = store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Bauxite", rigs="2",
                             density="Low", amount="High", lat="10.03", lon="20.0")
    app.on_pick(bare)
    pump()
    check("with nothing alike it says not measured yet", "not measured yet" in app.detail.cget("text"),
          app.detail.cget("text"))
    rows = STR.deposits(store, "Ega", "Ega 1", "1", crowd=app.crowd_figures().tonnes)
    cells = {r["commodity"]: A.deposit_cells(r)[4][0] for r in rows if not r["depleted"]}
    check("the table cell says it too", cells.get("Bauxite") == "not measured yet" and
          cells.get("Platinum", "").startswith("est. 90-120t"), cells)


@on_screen("the crowd's tonnes are asked for with the other figures")
def _follow():
    fake = app.community = FakeCommunity()
    app.crowd = None
    app.follow_crowd(time.time() + 99999)
    check("asked", ("tonnes", CR.TONNES_TAG) in fake.asked, fake.asked)
    app.take_crowd(CR.TONNES_TAG, True, json.dumps(GROUPS))
    check("and kept", app.crowd_figures().tonnes.range_for("Platinum", 4, "High") == (110, 140, 9))

    # The answer comes back through the same queue as every other one, and
    # is taken there: never shown raw on the status line, right or wrong.
    class _Worker:
        def __init__(self, rows):
            self.rows = list(rows)

        def drain(self):
            rows, self.rows = self.rows, []
            return rows

    said, real = [], app.worker
    app.say = lambda *args, **kwargs: said.append(args)
    try:
        app.crowd = None
        app.worker = _Worker([(CR.TONNES_TAG, True, json.dumps(GROUPS))])
        app.collect_results()
        check("the answer in the queue reaches the figures",
              app.crowd_figures().tonnes.range_for("Platinum", 4, "High") == (110, 140, 9))
        check("and nothing of it is put on the status line", said == [], said)
        app.worker = _Worker([(CR.TONNES_TAG, False, "could not reach the map")])
        app.collect_results()
        check("an answer that failed says nothing either", said == [], said)
        check("and the figures already held are kept",
              app.crowd_figures().tonnes.range_for("Platinum", 4, "High") == (110, 140, 9))
    finally:
        app.worker = real
        del app.say


@on_screen("D4: the catch-up goes once, and never again")
def _once():
    fake = app.community = FakeCommunity()
    app.watcher.cmdr = "CMDR Cee"
    store = app.store
    store.deposits[:] = []
    store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Iridium", rigs="3",
                      density="Medium", amount="", lat="11.0", lon="21.0",
                      cycles="2026-09-20=56;2026-10-02=48")
    app.settings["tonnes_catchup_done"] = False
    sent = app.send_tonnes_catchup()
    rows = [r for _c, chunk in fake.uploads for r in chunk]
    check("both earlier cycles were sent, each with its day", sent == 2 and sorted(
        (r["tonnes"], r["tonnes_on"]) for r in rows) == [(48, "2026-10-02"), (56, "2026-09-20")], rows)
    check("the deposit is sent as it stands, not as worked out", all(r.get("amount") == "" for r in rows), rows)
    check("a flag marks it done", app.settings.get("tonnes_catchup_done") is True)
    fake.uploads.clear()
    check("and it never goes again", app.send_tonnes_catchup() == 0 and not fake.uploads)
    app.settings["tonnes_catchup_done"] = False
    store.deposits[:] = []
    check("with nothing to send, nothing is sent", app.send_tonnes_catchup() == 0 and not fake.uploads)
    check("and it is marked done", app.settings.get("tonnes_catchup_done") is True)
    app.settings["tonnes_catchup_done"] = False
    app.community = FakeCommunity()
    app.community.ready = False
    store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Iridium", rigs="3",
                      density="Medium", lat="11.5", lon="21.0", cycles="2026-09-20=56")
    check("with sharing off nothing goes and it is not marked done",
          app.send_tonnes_catchup() == 0 and not app.settings.get("tonnes_catchup_done"))


print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
