"""1.2: Still there? and Due a check for other commanders' deposits.

Carried over from 1.10042 (package K) and asked again in "do all these",
19 Nov. Driving onto another commander's find, with none of yours under you,
asks once "Still there? UPDATE or MINED OUT", as your own do. UPDATE says it
is still there and MINED OUT that it is worked out; either goes to the
community map for everyone. Find's Due a check lists other commanders' finds
EDSMT has fetched as well as yours, each saying whose it is.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_12_theirs.py
"""
import inspect
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
# Never the real data folder: the app is loaded below.
import tempfile   # noqa: E402
os.environ["LOCALAPPDATA"] = os.path.join(tempfile.mkdtemp(prefix="edsmt-12-"), "appdata")

import edonline as EDO   # noqa: E402
import recheck as RC     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


NOW = time.time()


def ago(days):
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(NOW - days * 86400))


def theirs(n, days, cmdr="CMDR Ace", amount="High", worked_days=None, lat="10.000500"):
    row = {"id": "shared-%d" % n, "system": "Ega", "body": "Ega 1", "location": "1",
           "commodity": "Platinum", "rigs": "4", "amount": amount, "density": "High",
           "lat": lat, "lon": "20.000000", "cmdr": cmdr, "shared": True, "when": ago(days)}
    if worked_days is not None:
        row["worked_out_days"] = worked_days
    return row


HERE_AT = {"system": "Ega", "body": "Ega 1", "lat": 10.0, "lon": 20.0, "radius_m": 1500000.0}

print("== another commander's find, due a check by the same rule as yours ==")
check("seen 40 days ago: due", RC.due_rows([RC.shared_checkable(theirs(1, 40))], NOW, here=HERE_AT))
check("seen yesterday: not due", not RC.due_rows([RC.shared_checkable(theirs(2, 1))], NOW, here=HERE_AT))
back = RC.due_rows([RC.shared_checkable(theirs(3, 60, amount="Depleted", worked_days=30))], NOW, here=HERE_AT)
check("worked out a month ago: due a look", back and back[0]["deposit"]["id"] == "shared-3", back)
check("worked out two days ago: not yet", not RC.due_rows(
    [RC.shared_checkable(theirs(4, 60, amount="Depleted", worked_days=2))], NOW, here=HERE_AT))
check("one of yours is not turned into one of theirs", RC.shared_checkable({"id": "7", "when": ago(3)}) is None
      and RC.shared_checkable(None) is None)
row = RC.shared_checkable(theirs(5, 40))
check("the original row is left as it was", "recorded" not in theirs(5, 40) and row["recorded"])

print("== the map's sighting: UPDATE on someone else's find ==")


class Worker:
    def __init__(self):
        self.jobs = []

    def submit(self, tag, job):
        self.jobs.append((tag, job))


worker = Worker()
client = EDO.CommunityClient(worker)
client.configure("", enabled=True)
sent = []
real_post = EDO.post_json
EDO.post_json = lambda url, payload, **kw: sent.append((url, payload)) or {"ok": True, "worked_out": False}
try:
    check("a sighting is sent", client.report_seen("CMDR Bee", "Ega", "Ega 1", "1") is True)
    worker.jobs[-1][1]()
    url, payload = sent[-1]
    check("as the depletion report, worked out false and seen true",
          url.endswith("/v1/depletion") and payload["message"]["worked_out"] is False
          and payload["message"]["seen"] is True, payload)
    check("with the CMDR name", payload["header"]["uploaderID"] == "CMDR Bee")
    client.report_depletion("CMDR Bee", "Ega", "Ega 1", "1")
    worker.jobs[-1][1]()
    check("a worked-out report carries no sighting", "seen" not in sent[-1][1]["message"], sent[-1][1])
finally:
    EDO.post_json = real_post

print("== in the app ==")
try:
    import edsmt as A
except Exception as exc:   # noqa: BLE001
    print("  FAIL  the app did not load: %s" % exc)
    sys.exit(1)


class Thing:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Community:
    ready = can_read = True

    def __init__(self):
        self.calls = []

    def report_seen(self, *a):
        self.calls.append(("seen",) + a)
        return True

    def report_depletion(self, *a, **kw):
        self.calls.append(("out",) + a)
        return True


def new_app():
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.heard, app.flashes, app.lines = [], [], []
    app.speak = lambda line_id, **kw: app.heard.append(line_id) or True
    app.say = lambda text, *a, **kw: app.lines.append(text)
    app.flash = lambda *a, **kw: app.flashes.append(a)
    app.trouble = lambda *a, **kw: None
    app.here = lambda: ("Ega", "Ega 1")
    app.game = Thing(has_position=True, in_srv=True, lat=10.0, lon=20.0, radius_m=1500000.0)
    app.watcher = Thing(cmdr="CMDR Bee")
    app.community = Community()
    app.shared = {("ega", "ega 1"): {"at": NOW, "rows": [theirs(1, 40)]}}
    app.store = Thing(deposits=[], at=lambda *a: [])
    app.own_deposit_here = lambda commodity="": None
    app.save_settings = lambda: None
    app.crowd_figures = lambda: Thing(regrow_days=None, tonnes=None)
    app.redraw = lambda: None
    return app


app = new_app()
near = app.other_deposit_here()
check("another commander's find under you is found", near and near[0]["id"] == "shared-1", near)
mine = new_app()
mine.shared = {("ega", "ega 1"): {"at": NOW, "rows": [theirs(2, 40, cmdr="CMDR Bee")]}}
check("your own, back from the map, is not someone else's", mine.other_deposit_here() is None)
far = new_app()
far.shared = {("ega", "ega 1"): {"at": NOW, "rows": [theirs(3, 40, lat="10.010000")]}}
check("one 1 km away is not under you", far.other_deposit_here() is None)

app.follow_deposit(app.game)
check("driving onto it asks Still there?", app.flashes and app.flashes[-1][0] == RC.ASK
      and app.heard == ["still_there"], (app.flashes, app.heard))
check("saying whose it is and that the answer goes on the map",
      any("CMDR Ace" in line and "community map" in line for line in app.lines), app.lines)
check("asked once for this arrival", (app.follow_deposit(app.game) or True) and app.heard == ["still_there"])
check("UPDATE: still there, for everyone", app.answer_theirs(True) is True
      and app.community.calls[-1] == ("seen", "CMDR Bee", "Ega", "Ega 1", "1"), app.community.calls)
check("answered: not asked again", app.answer_theirs(True) is False)

app = new_app()
app.follow_deposit(app.game)
check("MINED OUT: worked out, for everyone", app.answer_theirs(False) is True
      and app.community.calls[-1][0] == "out" and app.heard[-1] == "mined_out", app.community.calls)

app = new_app()
app.follow_deposit(app.game)
app.game = Thing(has_position=True, in_srv=True, lat=10.02, lon=20.0, radius_m=1500000.0)
app.follow_deposit(app.game)
check("driving off unanswered: nothing goes on your own list",
      app.settings.get(RC.KEY, {}) == {}, app.settings.get(RC.KEY))

fresh = new_app()
fresh.shared = {("ega", "ega 1"): {"at": NOW, "rows": [theirs(4, 0.2)]}}
fresh.follow_deposit(fresh.game)
check("seen by someone today: not asked", fresh.heard == [] and not fresh.flashes)
gone = new_app()
gone.shared = {("ega", "ega 1"): {"at": NOW, "rows": [theirs(5, 40, amount="Depleted", worked_days=3)]}}
gone.follow_deposit(gone.game)
check("worked out: not asked", gone.heard == [])

check("UPDATE answers it", "self.answer_theirs(True)" in inspect.getsource(A.EDSMT.update_deposit_here))
check("MINED OUT answers it", "self.answer_theirs(False)" in inspect.getsource(A.EDSMT.mark_mined))

print("== Due a check lists theirs as well ==")
app = new_app()
rows = app.shared_due(NOW, HERE_AT)
check("another commander's old find is due", rows and rows[0]["deposit"]["id"] == "shared-1", rows)
check("saying whose it is", rows and "CMDR Ace" in rows[0]["words"], rows)
app.shared = {("ega", "ega 1"): {"at": NOW, "rows": [theirs(6, 40, cmdr="CMDR Bee")]}}
check("your own, back from the map, is not listed twice", app.shared_due(NOW, HERE_AT) == [])
check("the window takes them", "shared_due(" in inspect.getsource(A.FindWindow.search_due)
      if hasattr(A, "FindWindow") else False)
check("the map's answer keeps how long ago it was worked out",
      "worked_out_days" in inspect.getsource(A.EDSMT.take_shared))

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
