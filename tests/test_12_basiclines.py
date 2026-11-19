"""1.2: the new Basic lines said by the app (the rules: test_12_basiccues.py).

Each of the 17 lines approved 19 Nov 2026 is said where it belongs, once for
what it is about, and never twice in a row for the same thing:
value_top / value_best and rich_patch on marking, the value line and
nearly_out / plenty_left on driving onto a deposit, sell_here with the
SELLING HERE flash, hold_full / rhino_full_soon / ship_full_soon from the
fill timers, due_check near one of yours, guide_far, landed_marked,
pin_skipped, import_done, ribbon_earned from the community map, and
live_on / live_off with the Twitch live-status switch.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_12_basiclines.py
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

import basiccues as BC     # noqa: E402
import edonline as EDO     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


try:
    import edsmt as A
except Exception as exc:   # noqa: BLE001 - a missing display is reported, not raised
    print("  FAIL  the app did not load: %s" % exc)
    sys.exit(1)


class Thing:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Crowd:
    regrow_days = None
    tonnes = None


def new_app():
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.settings["voice_mode"] = True
    app.heard = []
    app.speak = lambda line_id, **kw: app.heard.append(line_id) or True
    app.say = lambda *a, **kw: None
    app.flash = lambda *a, **kw: None
    app.trouble = lambda *a, **kw: None
    app.crowd_figures = lambda: Crowd()
    return app


def source(name, cls=None):
    return inspect.getsource(getattr(cls or A.EDSMT, name))


PRICES = {"Platinum": 250000, "Osmium": 200000, "Rhodplumsite": 180000, "Iridium": 150000,
          "Samarium": 120000, "Water": 100}

print("== high value: on marking and on driving onto a deposit, once each ==")
app = new_app()
app.mine_price = lambda name: (PRICES.get(name, 0), "at Hub")
check("the best on the map", app.value_cue({"id": "d1", "commodity": "Platinum"}) == "value_best"
      and app.heard == ["value_best"], app.heard)
check("one of the top five", app.value_cue({"id": "d2", "commodity": "Iridium"}) == "value_top")
check("worth little: nothing", app.value_cue({"id": "d3", "commodity": "Water"}) == "")
check("never twice for the same deposit", app.value_cue({"id": "d1", "commodity": "Platinum"}) == ""
      and app.heard == ["value_best", "value_top"], app.heard)
check("a price lookup that breaks says nothing",
      (setattr(app, "mine_price", lambda n: 1 / 0) or app.value_cue({"id": "d9", "commodity": "Gold"}) == ""))

print("== rich patch on marking; how much is left on arriving ==")
app = new_app()
app.mine_price = lambda name: (0, "")
patch = [{"id": "p1", "patch": 1}, {"id": "p2", "patch": 1}, {"id": "p3", "patch": 1}, {"id": "p4", "patch": 2}]
app.patch_rows = lambda deposit: patch
check("marked in a top patch of three: rich patch",
      app.deposit_cues({"id": "p2", "commodity": "Water"}, marking=True) == ["rich_patch"], app.heard)
check("not in the top patch: nothing", app.deposit_cues({"id": "p4", "commodity": "Water"}, marking=True) == [])
app.left_now = lambda deposit: ((5, 10, 2, "yours"), (40, 60, 2, "yours"))
check("arriving at one nearly worked out", app.deposit_cues({"id": "p1", "commodity": "Water"}) == ["nearly_out"])
app.left_now = lambda deposit: ((50, 60, 2, "yours"), (50, 60, 2, "yours"))
check("arriving at one barely touched", app.deposit_cues({"id": "p3", "commodity": "Water"}) == ["plenty_left"])
check("and not again for it", app.deposit_cues({"id": "p3", "commodity": "Water"}) == [])
check("arriving is not marking: no rich patch on arrival",
      "rich_patch" not in app.deposit_cues({"id": "p1x", "commodity": "Water"}))
check("a deposit with no id: nothing", app.deposit_cues({"commodity": "Water"}, marking=True) == [])
check("marking says them", "self.deposit_cues(record, marking=True)" in source("mark_deposit"))
check("driving onto one says them", "self.deposit_cues(deposit)" in source("follow_deposit"))
check("the patch rows are the Sites window's own", "STR.deposits(" in source("patch_rows")
      and "golden_radius" in source("patch_rows"))
check("left from what it holds less what was mined", "STR.left(" in source("left_now")
      and "STR.holds(" in source("left_now"))

print("== selling here: with the SELLING HERE flash, once a station ==")
app = new_app()
app.best_price = lambda name: (PRICES.get(name, 0), None, "fresh")
found = {"station": "Hub", "system": "Ega", "parts": [{"commodity": "Platinum", "sell": 250000}]}
check("the best price known: sell here", app.sell_cue(found) is True and app.heard == ["sell_here"])
check("not again at the same station", app.sell_cue(found) is False)
check("under the best known: nothing", app.sell_cue(
    {"station": "Low", "system": "Ega", "parts": [{"commodity": "Platinum", "sell": 1000}]}) is False)
check("said with the flash", "self.sell_cue(found)" in source("presale_now"))

print("== the Rhino and the ship filling ==")
app = new_app()
app.watcher = Thing(in_srv=True, srv_total=60)
app.ship_card = lambda: {"known": True, "capacity": 400, "tonnes": 100}
app.fill_clock = Thing(rate=lambda now: 300.0)
app.settings.update(voice_theme="ship_computer", voice_detail="normal")
check("five minutes from full", app.fill_cues(now=1000.0) == ["rhino_full_soon"], app.heard)
app.watcher.srv_total = 72
check("full", app.fill_cues(now=1010.0) == ["hold_full"])
check("not again this load", app.fill_cues(now=1020.0) == [])
app.watcher.in_srv = False
check("out of the Rhino: nothing", app.fill_cues(now=1030.0) == [])
her = new_app()
her.watcher = Thing(in_srv=True, srv_total=72)
her.ship_card = lambda: None
her.fill_clock = Thing(rate=lambda now: 300.0)
her.settings.update(voice_theme="celestia", voice_detail="chatty")
check("Celestia, Chatty: her own reaction says the Rhino is full, not twice",
      her.fill_cues(now=1000.0) == [])
check("every tick looks", "self.fill_cues()" in source("tick"))

print("== due a check: one of yours on this body, within 2 km ==")
app = new_app()
now = time.time()
old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 40 * 86400))
dep = {"id": "old1", "system": "Ega", "body": "Ega 1", "location": "1", "commodity": "Platinum",
       "lat": "10.001000", "lon": "20.000000", "amount": "High", "recorded": old}
app.store = Thing(deposits=[dep])
app.here = lambda: ("Ega", "Ega 1")
app.game = Thing(has_position=True, lat=10.0, lon=20.0, radius_m=1500000.0)
check("the setup is due by the Due a check window's rule", A.RC.due_rows(
    [dep], now, here={"system": "Ega", "body": "Ega 1", "lat": 10.0, "lon": 20.0, "radius_m": 1500000.0}))
check("said near it", app.due_cue(now=now) == "due_check" and app.heard == ["due_check"], app.heard)
check("looked at once a minute, not every tick", app.due_cue(now=now + 5) == "")
check("and once for that deposit", app.due_cue(now=now + 120) == "")
app2 = new_app()
app2.store, app2.here, app2.game = app.store, app.here, app.game
app2._on_deposit = "old1"
check("not for the one you are standing on (Still there? asks about that)", app2.due_cue(now=now) == "")
check("every tick looks", "self.due_cue()" in source("tick"))

print("== the other places ==")
check("Guide me there to another body says so", "self.speak(\"guide_far\")" in source("guide_far"))
check("Skip this pin says the pin was skipped", "self.speak(\"pin_skipped\")" in source("skip_pin")
      and "self.speak(\"next_pin\")" not in source("skip_pin"))
check("touchdown says waypoint one is marked, in the recorded voice",
      "speak(\"landed_marked\")" in inspect.getsource(A.EDSMT.wp_tell_landed))
check("an import that finishes says so", "self.app.speak(\"import_done\")" in source("do_import", A.ImportWindow))

print("== guide_far, said only for another body ==")
app = new_app()
saved = A.save_settings
A.save_settings = lambda settings: None
try:
    app.here = lambda: ("Ega", "Ega 1")
    app.far_status = lambda: ("", "on the way")
    app.guide_to = lambda deposit: None
    app.pick_deposit = lambda deposit, **kw: None
    app.show_map = lambda: None
    far = {"id": "f1", "system": "Ega", "body": "Ega 3", "location": "1", "commodity": "Gold",
           "lat": "1.0", "lon": "2.0"}
    app.guide_far(far)
    check("another body: said", app.heard == ["guide_far"], app.heard)
    app.heard = []
    app.guide_far(dict(far, id="f2", body="Ega 1"))
    check("this body: not", app.heard == [], app.heard)
finally:
    A.save_settings = saved

print("== ribbons: asked now and then, said when a new step comes ==")


class Worker:
    def __init__(self):
        self.jobs = []

    def submit(self, tag, job):
        self.jobs.append((tag, job))


worker = Worker()
client = EDO.CommunityClient(worker)
client.configure("", enabled=False)
check("asking is reading, not sharing: no switch needed", client.ribbons("CMDR Test") is True)
check("the commander's own ribbons, by name", worker.jobs and worker.jobs[0][0] == EDO.RIBBONS_TAG)
real_get = EDO.get_json
seen = []
EDO.get_json = lambda url, **kw: seen.append(url) or {"earned": 4}
try:
    answer = json.loads(worker.jobs[0][1]())
    check("from the map's public ribbons page", seen and seen[0].endswith("/v1/public/cmdrs/CMDR%20Test/ribbons")
          and answer == {"earned": 4}, seen)

    def none(url, **kw):
        raise RuntimeError("HTTP 404")
    EDO.get_json = none
    client.ribbons("CMDR New")
    check("nothing on the map yet: no steps", json.loads(worker.jobs[-1][1]()) == {"earned": 0})
finally:
    EDO.get_json = real_get
check("no name: not asked", client.ribbons("") is False)

app = new_app()
app.watcher = Thing(cmdr="CMDR Test")
app.community = client
before = len(worker.jobs)
check("asked with Voice Mode on", app.ask_ribbons(now=5000.0) is True and len(worker.jobs) == before + 1)
check("not again for ten minutes", app.ask_ribbons(now=5000.0 + 60) is False)
check("then again", app.ask_ribbons(now=5000.0 + A.RIBBON_LOOK_S + 1) is True)
app.settings["voice_mode"] = False
check("Voice Mode off: not asked", app.ask_ribbons(now=99999.0) is False)
check("the first answer only notes the count", app.take_ribbons(True, json.dumps({"earned": 4})) == ""
      and app.heard == [])
check("the same count: nothing", app.take_ribbons(True, json.dumps({"earned": 4})) == "")
check("one more step: New ribbon earned", app.take_ribbons(True, json.dumps({"earned": 5})) == "ribbon_earned"
      and app.heard == ["ribbon_earned"])
check("a failed or broken answer: nothing", app.take_ribbons(False, "x") == ""
      and app.take_ribbons(True, "not json") == "")
app.watcher.cmdr = "CMDR Other"
check("another commander's count is theirs, not a new ribbon",
      app.take_ribbons(True, json.dumps({"earned": 9})) == "" and app.heard == ["ribbon_earned"])
check("the answer is handed over", "EDO.RIBBONS_TAG" in source("collect_results")
      and "self.take_ribbons(ok, message)" in source("collect_results"))
check("every tick may ask", "self.ask_ribbons()" in source("tick"))

print("== the Twitch live-status switch ==")
app = new_app()
app.settings["twitch_status"] = False
check("at start: nothing said", app.live_cue() == "")
app.settings["twitch_status"] = True
check("switched on: Live status on", app.live_cue() == "live_on" and app.heard == ["live_on"])
check("left on: nothing more", app.live_cue() == "")
app.settings["twitch_status"] = False
check("switched off: Live status off", app.live_cue() == "live_off" and app.heard == ["live_on", "live_off"])
check("looked at with the live status", "self.live_cue()" in source("follow_now"))

print("== shipped ==")
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    text = open(os.path.join(REPO, "build", spec), encoding="utf-8").read()
    check("%s bundles basiccues" % spec, '"basiccues"' in text)
check("the whole suite runs these", "test_12_basiclines.py" in open(os.path.join(HERE, "run_all.py"),
                                                                     encoding="utf-8").read()
      and "test_12_basiccues.py" in open(os.path.join(HERE, "run_all.py"), encoding="utf-8").read())

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
