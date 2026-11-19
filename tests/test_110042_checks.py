"""1.10042: keeping the map right (E1, E3, E4, E6).

  E4  a depleted mark is kept, never lifted on a timer; once the time our own
      reports measured has passed, the deposit reads "may be back - needs a
      check" and joins the Due a check list;
  E6  the first tonne refined at a deposit marked worked out takes the mark
      off, and the deposit's line says when it is expected back;
  E1  driving onto a deposit you have marked asks once "Still there? UPDATE or
      MINED OUT"; leaving without answering says one line and puts the deposit
      on a visited-not-updated list, shown at the next start with one-click
      answers - a small window that never blocks the start and is not there
      when the list is empty;
  E3  a Due a check list in Find: deposits nobody has confirmed for a while,
      nearest first.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_checks.py
"""
import faulthandler
import json
import os
import sys
import tempfile
import time
import types

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-checks42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import regrowth as RG     # noqa: E402
import recheck as RC      # noqa: E402
import crowd as CR        # noqa: E402
import finder as FD       # noqa: E402
import voice as VO        # noqa: E402

fails = []
DAY = 86400.0
BASE = 1_760_000_000.0


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


def worked(**extra):
    row = {"id": "d1", "system": "Ega", "body": "Ega 1", "location": "1", "commodity": "Platinum",
           "amount": "Depleted", "depleted_at": RG.stamp(BASE), "rechecks": "", "mined": "",
           "notes": "", "lat": "10.0", "lon": "20.0", "recorded": RG.stamp(BASE - 30 * DAY)}
    row.update(extra)
    return row


MEASURED = {"reports": 12, "commanders": 5, "low_days": 16.0, "high_days": 28.4, "measured": True}


@section("E4: the mark is kept, and after the measured time it reads may be back")
def _e4():
    check("nothing lifts a mark on a timer any more",
          not hasattr(RG, "expire_marks") and not hasattr(RG, "expiry_changes"))
    row = worked(rechecks=RG.stamp(BASE + 15 * DAY))
    info = RG.standing(row, BASE + 40 * DAY)
    check("a look found it empty; weeks later the mark is still on and it is due another",
          RG.depleted(row) and info["state"] == "look" and info["due"], info)
    info = RG.standing(worked(), BASE + 15.9 * DAY, regrow_days=16.0)
    check("before the measured time: not due", not info["due"], info)
    info = RG.standing(worked(), BASE + 16.1 * DAY, regrow_days=16.0)
    check("after it: may be back - needs a check", info["state"] == "back" and info["due"]
          and info["text"] == "may be back - needs a check", info)
    info = RG.standing(worked(), BASE + 9 * DAY, regrow_days=None)
    check("with nothing measured the old fortnight still stands", info["state"] == "fresh", info)
    info = RG.standing(worked(rechecks=RG.stamp(BASE + 17 * DAY)), BASE + 18 * DAY, regrow_days=16.0)
    check("a check that found it empty puts the next one off", not info["due"], info)
    crowd = CR.Crowd()
    crowd.take(CR.REGROWTH_TAG, {"all": dict(MEASURED), "by_commodity": []})
    check("the crowd gives the measured days", crowd.regrow_days("Platinum") == 16.0, crowd.regrow_days("Platinum"))
    check("none until measured", CR.Crowd().regrow_days("Platinum") is None)
    crowd.take(CR.REGROWTH_TAG, {"all": dict(MEASURED, measured=False), "by_commodity": []})
    check("and none while it says not measured yet", crowd.regrow_days("Platinum") is None)


@section("E6: the first tonne takes the mark off, and the line says when it is expected back")
def _e6():
    changes = RG.first_tonne_changes(worked(mined="Platinum:1"), BASE + 20 * DAY)
    check("the mark off, the amount unread, the dates cleared",
          changes["amount"] == "" and changes["depleted_at"] == "" and changes["rechecks"] == "", changes)
    check("and the note says why", "first tonne" in changes["notes"].lower(), changes["notes"])
    crowd = CR.Crowd()
    crowd.take(CR.REGROWTH_TAG, {"all": dict(MEASURED), "by_commodity": []})
    line = crowd.expected_line(worked(), BASE + 2 * DAY)
    check("a worked-out deposit says when it is expected back", "expected back" in line
          and "12 reports" in line, line)
    check("with the dates", time.strftime("%d %b", time.gmtime(BASE + 16 * DAY)).lstrip("0") in line
          or time.strftime("%d %b", time.gmtime(BASE + 16 * DAY)) in line, line)
    check("past the time it says may be back", "may be back - needs a check"
          in crowd.expected_line(worked(), BASE + 20 * DAY))
    check("nothing for a deposit that is not worked out", crowd.expected_line(worked(amount="High"), BASE) == "")
    check("nothing while nothing is measured", CR.Crowd().expected_line(worked(), BASE) == "")


@section("E1: the question, the line on leaving, and the visited list")
def _e1():
    check("the question", RC.ASK == "Still there? UPDATE or MINED OUT")
    check("it is spoken by the Windows voice, no recording",
          VO.SPOKEN_ONLY.get("still_there") and "update" in VO.SPOKEN_ONLY["still_there"].lower())
    check("leaving without answering is one line naming the deposit",
          "Platinum" in RC.left_line("Platinum") and "UPDATE" in RC.left_line("Platinum"))
    settings = {}
    visits = RC.Visits(settings)
    check("empty to begin with", visits.ids() == [])
    visits.add("d1", BASE)
    visits.add("d2", BASE + 5)
    visits.add("d1", BASE + 9)
    check("each deposit once, in the order first visited", visits.ids() == ["d1", "d2"], visits.ids())
    check("kept in the settings it was given", set(settings.get("visited_not_updated", {})) == {"d1", "d2"})
    visits.clear("d1")
    check("an answer takes it off", visits.ids() == ["d2"])
    rows = visits.pending([worked(id="d2"), worked(id="d9")])
    check("pending is the deposits still in the store", [r["id"] for r in rows] == ["d2"], rows)
    check("one gone from the store is dropped from the list", visits.ids() == ["d2"] and
          RC.Visits({"visited_not_updated": "junk"}).ids() == [])
    check("answering stamps the check", RC.checked_changes(BASE)["checked_at"] == RG.stamp(BASE))
    one = {"commodity": "Iridium", "rigs": "4", "amount": "Medium", "density": "High", "system": "Col 285",
           "body": "Col 285 BC 2", "location": "21", "lat": "14.013", "lon": "-79.8287"}
    two = dict(one, rigs="2", amount="High", lat="14.02", lon="-79.81")
    first = RC.visit_lines(one, "1.24 km NE 045", 340.0, lambda m: "%.0f m" % m)
    check("a row of the visited list says what is recorded for the deposit",
          first[0] == "Iridium - 4 rigs, Amount Medium, Density High", first)
    check("then where it lies: from the location's centre and from you",
          first[1] == "Signal 21: 1.24 km NE 045 from the centre, 340 m from you", first)
    check("then the body and its position, as the Rhino shows it",
          first[2] == "Col 285 BC 2 at 14.0130, -79.8287", first)
    second = RC.visit_lines(two, "900 m SW 225", None, str)
    check("two deposits of one commodity in one location do not read the same",
          second != first and second[0] == "Iridium - 2 rigs, Amount High, Density High", second)
    bare = RC.visit_lines({"commodity": "", "body": "", "system": "Dee", "location": ""}, "-", None, str)
    check("with nothing recorded it still reads, and says nothing it does not know",
          bare == ["Deposit", "Signal -", "Dee"], bare)
    check("at the centre is said as it is",
          RC.visit_lines(one, "at the centre", None, str)[1] == "Signal 21: at the centre")
    check("one rig is one rig", RC.visit_lines(dict(one, rigs="1"), "", None, str)[0].startswith("Iridium - 1 rig,"))
    here = {"system": "Col 285", "body": "Col 285 BC 2", "lat": 14.013, "lon": -79.8287, "radius_m": 1000000.0}
    check("how far it is from you is measured on its own body only",
          RC.away_metres(one, here) is not None and RC.away_metres(one, here) < 1.0
          and RC.away_metres(one, dict(here, body="Col 285 BC 3")) is None and RC.away_metres(one, None) is None)


@section("E3: due a check, nearest first")
def _e3():
    near = worked(id="a", amount="High", depleted_at="", recorded=RG.stamp(BASE - 10 * DAY), lat="10.0", lon="20.0")
    far = worked(id="b", amount="High", depleted_at="", recorded=RG.stamp(BASE - 20 * DAY), lat="10.5", lon="20.0",
                 commodity="Gold")
    other = worked(id="c", amount="High", depleted_at="", recorded=RG.stamp(BASE - 40 * DAY), body="Ega 2",
                   commodity="Iron")
    fresh = worked(id="e", amount="High", depleted_at="", recorded=RG.stamp(BASE - 1 * DAY), commodity="Tin")
    seen = worked(id="f", amount="High", depleted_at="", recorded=RG.stamp(BASE - 60 * DAY),
                  checked_at=RG.stamp(BASE - 2 * DAY), commodity="Lead")
    spent = worked(id="g", commodity="Silver", depleted_at=RG.stamp(BASE - 5 * DAY))
    back = worked(id="h", commodity="Copper", depleted_at=RG.stamp(BASE - 25 * DAY), lon="20.2")
    here = {"system": "Ega", "body": "Ega 1", "lat": 10.0, "lon": 20.0, "radius_m": 1_000_000.0}
    rows = RC.due_rows([far, near, other, fresh, seen, spent, back], BASE, regrow_days=16.0, here=here)
    got = [r["deposit"]["id"] for r in rows]
    check("those nobody has checked for a while, and the one that may be back; not fresh, not checked, not mid-wait",
          sorted(got) == ["a", "b", "c", "h"], got)
    check("nearest first: on this body by distance, then other bodies", got == ["a", "h", "b", "c"], got)
    check("the one that may be back says so", [r["words"] for r in rows if r["deposit"]["id"] == "h"] ==
          ["may be back - needs a check"], rows)
    check("the others say how long", [r["words"] for r in rows if r["deposit"]["id"] == "a"] ==
          ["not checked for 10 days"], rows)
    check("a deposit worked out with nothing measured is not due until a fortnight",
          RC.due_rows([spent], BASE, regrow_days=None, here=here) == [])
    check("Find has the search", any(key == "due" for key, _label in FD.MODES) and FD.mode_key("Due a check") == "due")
    check("it is a search of its own records, with its own table", FD.mode_of_kind("due") == "due")


@section("E5: plain how-to, the same words in the guide, Help and the welcome")
def _e5():
    guide = open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
    check("the guide has a Keeping the map right section", "\n## Keeping the map right\n" in guide
          or "\n### Keeping the map right\n" in guide)
    flat = " ".join(guide.split())
    for part in RC.HOWTO_WORDS.split("\n\n"):
        check("the guide says it in the same words: %s..." % part[:40], " ".join(part.split()) in flat)
    check("short: a handful of paragraphs", 3 <= len(RC.HOWTO_WORDS.split("\n\n")) <= 6)
    check("it names the question, the list, the search and the points",
          all(word in RC.HOWTO_WORDS for word in ("Still there? UPDATE or MINED OUT", "Due a check",
                                                  "may be back", "Site checker")))
    check("and says nothing the public tree must not", not any(w in RC.HOWTO_WORDS for w in (
          "serv" + "er settings", "DECIS" + "IONS")))


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
        self.uploads, self.reports = [], []

    def upload(self, cmdr, rows):
        self.uploads.append((cmdr, rows))
        return True

    def report_regrowth(self, cmdr, message, tag="regrowth-share"):
        self.reports.append(message)
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
    R = 1_000_000.0
    app.here = lambda: ("Ega", "Ega 1")
    app.store.set_location("Ega", "Ega 1", "1", lat=10.0, lon=20.0, radius_m=R)
    app.watcher.cmdr = "CMDR Cee"
    app.community = FakeCommunity()
    said, flashed, spoken = [], [], []
    app.say = lambda text, colour=None, *a, **k: said.append(text)
    app.flash = lambda title, detail="", colour=None: flashed.append((title, detail)) or True
    app.speak = lambda line, *a, **k: spoken.append(line) or True


def on_deposit(row, in_srv=True, moving_away=False):
    lat, lon = (10.0, 20.0 + (5.0 if moving_away else 0.0)) if row is None else (
        float(row["lat"]), float(row["lon"]))
    app.game = types.SimpleNamespace(has_position=True, in_srv=in_srv, lat=lat, lon=lon, radius_m=R,
                                     detected_type="", detected_density="", heading=None,
                                     body_profile=lambda *a, **k: {"planet_class": "", "gravity": 0, "temperature_k": 0, "volcanism": ""}, mining_signals=lambda: 0,
                                     target_signal="", landed=False)
    return app.game


@on_screen("the live status for the Twitch bot goes only with its switch on")
def _live_status():
    sent = []

    class Link:
        ready = True

        def send_now(self, cmdr, status, tag=""):
            sent.append((cmdr, status))
            return True

        def __getattr__(self, name):
            return lambda *args, **kwargs: True

    held = (app.community, app.watcher, app.game)
    app.community, app.game = Link(), None
    app.watcher = types.SimpleNamespace(cmdr="Tester", ranks={"Combat": 8, "Trade": 3},
                                        ship_label="Panther Clipper Mk II", ship_name="Dig Deep",
                                        ship_type="panthermkii")
    try:
        check("the switch is off to begin with", A.DEFAULT_SETTINGS.get("twitch_status") is False)
        app.settings["twitch_status"] = False
        app._now_on = False
        check("off, nothing is sent", app.follow_now(1000.0) is False and sent == [], sent)
        app.settings["twitch_status"] = True
        check("on, the first tick sends", app.follow_now(1000.0) is True and len(sent) == 1, sent)
        cmdr, status = sent[-1]
        check("for the commander in the journal", cmdr == "Tester", cmdr)
        check("with the ship and the ranks by name",
              status["ship"] == {"type": "Panther Clipper Mk II", "name": "Dig Deep"}
              and status["ranks"]["combat"] == "Elite" and status["ranks"]["trade"] == "Dealer", status)
        check("the six parts and no position", sorted(status) == ["body", "edsmt", "ranks", "session", "ship", "system"]
              and status["edsmt"]["version"] == A.APP_VERSION, sorted(status))
        check("not again inside half a minute", app.follow_now(1010.0) is False and len(sent) == 1)
        check("and again after it", app.follow_now(1031.0) is True and len(sent) == 2)
        app.settings["twitch_status"] = False
        check("switched off, it is taken down, once",
              app.follow_now(1032.0) is True and sent[-1] == ("Tester", None)
              and app.follow_now(1033.0) is False and len(sent) == 3, sent[-2:])
    finally:
        app.community, app.watcher, app.game = held
        app.settings["twitch_status"] = False


@on_screen("E1: asked once on driving onto a known deposit, one line on leaving")
def _drive():
    app.settings["visited_not_updated"] = {}
    app.store.deposits[:] = []
    row = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Platinum", rigs="4",
                                density="High", amount="High", lat="10.0", lon="20.0")
    said.clear(); flashed.clear(); spoken.clear()
    # The boxes still hold the last deposit worked on.
    for key, value in (("commodity", "Gold"), ("rigs", "2"), ("amount", "Low"), ("density", "Low")):
        app.fields[key].set(value)
    state = on_deposit(row)
    app.follow_deposit(state)
    check("the overlay asks", any(RC.ASK in t or RC.ASK in d for t, d in flashed), flashed)
    boxes = [app.fields[key].get() for key in ("commodity", "rigs", "amount", "density")]
    check("the boxes on the left show what is recorded for the deposit you drove onto",
          boxes == ["Platinum", "4", "High", "High"], boxes)
    check("and the line that says it was picked says so", any("boxes on the left" in t for t in said), said)
    app.fields["amount"].set("Low")
    app.follow_deposit(state)
    check("staying on it, a box you changed is left as you set it", app.fields["amount"].get() == "Low")
    app.fields["amount"].set("High")
    check("and the voice says the question once", spoken.count("still_there") == 1, spoken)
    app.follow_deposit(state)
    check("not again while you stay", spoken.count("still_there") == 1 and len(flashed) == 1, (spoken, flashed))
    app.follow_deposit(on_deposit(None, moving_away=True))
    check("leaving without answering is one line", sum(1 for t in said if "without UPDATE" in t) == 1, said)
    check("and the deposit is on the visited list", app.visits.ids() == [row["id"]], app.visits.ids())
    # Answering: UPDATE and MINED OUT while the question stands.
    said.clear(); spoken.clear(); flashed.clear()
    app.follow_deposit(on_deposit(row))
    check("asked again on the next visit", spoken.count("still_there") == 1, spoken)
    app.selected = row
    app.mark_mined()
    app.follow_deposit(on_deposit(None, moving_away=True))
    check("MINED OUT is an answer: nothing said on leaving, and off the list",
          not any("without UPDATE" in t for t in said) and app.visits.ids() == [], (said, app.visits.ids()))
    check("and it is stamped as checked", [d for d in app.store.deposits if d["id"] == row["id"]][0].get("checked_at"))
    row2 = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Gold", rigs="2",
                                 density="Low", amount="Medium", lat="10.0", lon="20.01")
    app.follow_deposit(on_deposit(row2))
    said.clear()
    app.fields["amount"].set("Low")
    app.update_deposit_here()
    now = [d for d in app.store.deposits if d["id"] == row2["id"]][0]
    check("UPDATE after driving on changes only the box you changed: the last deposit's rigs and density are not written onto this one",
          (now.get("commodity"), str(now.get("rigs")), now.get("density"), now.get("amount")) == ("Gold", "2", "Low", "Low"),
          (now.get("commodity"), now.get("rigs"), now.get("density"), now.get("amount")))
    app.follow_deposit(on_deposit(None, moving_away=True))
    check("UPDATE is an answer too", not any("without UPDATE" in t for t in said) and app.visits.ids() == [],
          (said, app.visits.ids()))
    before = spoken.count("still_there")
    app.follow_deposit(on_deposit(row2, in_srv=False))
    check("on foot nothing is asked", spoken.count("still_there") == before, (before, spoken))


@on_screen("the visited list at the next start: one-click answers, never blocking, nothing when empty")
def _list():
    app.store.deposits[:] = []
    a = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Iron", rigs="3",
                              density="Low", amount="High", lat="10.0", lon="20.0")
    b = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Tin", rigs="3",
                              density="Low", amount="High", lat="10.0", lon="20.02")
    app.settings["visited_not_updated"] = {}
    check("an empty list opens nothing", app.show_visited_list() is None)
    app.visits.add(a["id"], time.time())
    app.visits.add(b["id"], time.time())
    window = app.show_visited_list()
    pump()
    check("a window opens, and is not modal", window is not None and window.winfo_exists()
          and not window.grab_current(), window)
    check("it has the three answers for each deposit", set(window.button_texts()) >= {"Still there", "Mined out", "Skip"},
          window.button_texts())
    app.community.uploads.clear()
    window.answer(a["id"], "still")
    pump()
    check("Still there is a check: shared as it stands and stamped", app.community.uploads
          and [d for d in app.store.deposits if d["id"] == a["id"]][0].get("checked_at"), app.community.uploads)
    check("and the deposit leaves the list", app.visits.ids() == [b["id"]], app.visits.ids())
    window.answer(b["id"], "skip")
    pump()
    check("Skip takes it off without a check", app.visits.ids() == []
          and not [d for d in app.store.deposits if d["id"] == b["id"]][0].get("checked_at"))
    check("with the list empty the window closes itself", not window.winfo_exists(), None)
    app.visits.add(a["id"], time.time())
    window = app.show_visited_list()
    app.selected = None
    window.answer(a["id"], "mined")
    pump()
    row = [d for d in app.store.deposits if d["id"] == a["id"]][0]
    check("Mined out marks it worked out", str(row.get("amount")).lower() == "depleted", row)
    for name in ("start_checks", "show_visited_list"):
        check("%s is wired in" % name, name in A.EDSMT.__dict__)


@on_screen("the visited list says which deposit each row is")
def _which():
    app.store.deposits[:] = []
    a = app.store.add_deposit(system="Ega", body="Ega 1", location="21", commodity="Iridium", rigs="4",
                              density="High", amount="Medium", lat="10.0", lon="20.0")
    b = app.store.add_deposit(system="Ega", body="Ega 1", location="21", commodity="Iridium", rigs="2",
                              density="Low", amount="High", lat="10.0", lon="20.02")
    app.settings["visited_not_updated"] = {}
    app.visits.add(a["id"], time.time())
    app.visits.add(b["id"], time.time() + 1)
    window = app.show_visited_list()
    pump()
    texts = window.row_texts()
    check("two Iridium deposits in one location are two rows that read differently",
          len(texts) == 2 and texts[0] != texts[1], texts)
    check("each says its rigs, amount and density", len(texts) == 2
          and "4 rigs, Amount Medium, Density High" in texts[0]
          and "2 rigs, Amount High, Density Low" in texts[1], texts)
    check("and its signal and position", len(texts) == 2 and "Signal 21" in texts[0]
          and "10.0000, 20.0000" in texts[0] and "10.0000, 20.0200" in texts[1], texts)
    check("each row has Show beside the three answers", window.button_texts().count("Show") == 2,
          window.button_texts())
    app.selected = None
    window.show(b["id"])
    pump()
    check("Show picks that deposit in the main window",
          app.selected is not None and app.selected.get("id") == b["id"], app.selected)
    check("and leaves it on the list", app.visits.ids() == [a["id"], b["id"]], app.visits.ids())
    window.destroy()
    app.settings["visited_not_updated"] = {}


@on_screen("E6 and E4 in the app: the first tonne takes the mark off; the card says when it is back")
def _app_e6():
    app.store.deposits[:] = []
    app.community = fake = FakeCommunity()
    app.crowd_figures().take(CR.REGROWTH_TAG, {"all": dict(MEASURED), "by_commodity": []})
    row = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Platinum", rigs="4",
                                density="Medium", amount="Depleted", lat="10.0", lon="20.0",
                                depleted_at=RG.stamp(time.time() - 30 * DAY))
    app.selected = row
    app.on_pick(row)
    pump()
    card = app.detail.cget("text")
    check("the card says it is expected back, or may be back", "may be back - needs a check" in card
          or "expected back" in card, card)
    note = {"in_srv": True, "lat": 10.0, "lon": 20.0, "radius_m": R, "system": "Ega", "body": "Ega 1",
            "commodity": "Platinum", "when": RG.stamp(time.time())}
    app.credit_refined(note)
    pump()
    now = [d for d in app.store.deposits if d["id"] == row["id"]][0]
    check("the first tonne takes the mark off", not RG.depleted(now), now.get("amount"))
    check("and it was told to the community map as a regrowth report", len(fake.reports) == 1
          and fake.reports[0]["how"] == "refined", fake.reports)
    check("the tonne counts toward the next cycle", "Platinum:1" in str(now.get("mined")), now.get("mined"))


@on_screen("E5 in the app: Help and the welcome carry the how-to")
def _app_e5():
    labels = [app.help_menu.entrycget(i, "label") for i in range(app.help_menu.index("end") + 1)
              if app.help_menu.type(i) == "command"]
    check("Help has the entry", RC.HOWTO_TITLE in " ".join(labels), labels)
    window = app.open_keeping_right()
    pump()
    check("it opens a window with the words", window is not None and window.winfo_exists()
          and RC.HOWTO_WORDS.split("\n\n")[0] in window.text_shown(), None)
    window.destroy()
    welcome = app.show_welcome(force=True)
    pump()
    texts = []

    def walk(widget):
        for child in widget.winfo_children():
            try:
                texts.append(str(child.cget("text")))
            except Exception:
                pass
            walk(child)
    walk(welcome)
    check("the welcome carries it too", any(RC.HOWTO_TITLE.lower() in t.lower() for t in texts) and
          any(RC.HOWTO_WORDS.split("\n\n")[0] in t for t in texts), [t[:30] for t in texts][-12:])
    welcome.destroy()


@on_screen("E3 in the app: the Due a check search draws its own records")
def _app_e3():
    app.store.deposits[:] = []
    for i, name in enumerate(("Iron", "Tin")):
        app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity=name, rigs="3",
                              density="Low", amount="High", lat="10.0", lon="%.2f" % (20 + i * 0.01),
                              recorded=RG.stamp(time.time() - 30 * DAY))
    on_deposit(None)
    window = app.open_find() if hasattr(app, "open_find") else None
    check("Find opens", window is not None)
    window.set_mode("due")
    window.search_due()
    pump()
    texts = [r["deposit"]["commodity"] for r in window._rows]
    check("two due, nearest first", texts == ["Iron", "Tin"], texts)
    check("it is the table of its own kind", window._kind == "due")
    window.destroy()


print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
