"""1.10042: the scope says more, and the rig planner and the chat do more.

Asked for on the scope (#369): a scale bar, "centre 4.1 km NE" kept on it,
the swept ground in km2, the keys in its hint behind a switch - with the
zoom key and the rig planner's key named - and the zoom step kept across a
restart. With them:

  - the map's layer switches apply to the scope too, the waypoint pointer is
    a line with a dot there as well, and you are drawn at the size set;
  - at 2x and 4x, with its switch on, lines from deposit to deposit with
    their lengths;
  - a wingmate's collected rig stays on the scope, dashed;
  - "skip this pin" in the rig planner: a key, a joystick button and a chat
    word, like every other action;
  - chat words for log signal, border, zoom and plan rigs, so a session
    with no global keys needs no joystick.

The scope is drawn on a canvas that only writes down what it is asked to
draw, so most of this needs no display.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_scope.py
"""
import faulthandler
import io
import os
import sys
import tempfile

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-scope42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import planview as PV     # noqa: E402
import overlay as OV      # noqa: E402
import mapkey as MK       # noqa: E402
import chattags as CT     # noqa: E402
import inputdev as IND    # noqa: E402
import inputmix as IM     # noqa: E402
import rigplan as RP      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    """Run the function under it; an exception is one failure, named."""
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


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


class Canvas:
    """Writes down what it is asked to draw."""

    def __init__(self):
        self.calls = []

    def delete(self, *_a):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kw):
            self.calls.append((name, args, kw))
        return record


class Window:
    def __init__(self, size=420):
        self.size = size

    def winfo_width(self):
        return self.size

    def winfo_height(self):
        return self.size

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


class App:
    def colour_for(self, name):
        return "#ff7a18"


ROWS = [{"id": "1", "type": "Platinum", "range_m": 300.0, "bearing": 45.0, "rigs": 4, "location": "2"},
        {"id": "2", "type": "Platinum", "range_m": 520.0, "bearing": 80.0, "rigs": 2, "location": "2"},
        {"id": "3", "type": "Painite", "range_m": 450.0, "bearing": 300.0, "rigs": 2, "location": "2"}]
SURVEY = {"centre": (0.0, 0.0), "border_m": 1500.0, "rings": [500.0, 1000.0],
          "gaps": [{"east": 900.0, "north": -300.0, "area_km2": 0.4}],
          "points": [], "scan_m": 500.0, "percent": 83, "painted_km2": 2.44}
GUIDE = {"wp": {"complete": False, "text": "WP 2/3: 849 m, bearing 045", "bearing": 45.0,
                "range_m": 849.0, "n": 2, "total": 3, "arrive_m": 250.0,
                "points": [{"n": 1, "east": 0.0, "north": 0.0, "state": "done", "landed": True},
                           {"n": 2, "east": 600.0, "north": 600.0, "state": "current"},
                           {"n": 3, "east": -600.0, "north": -700.0, "state": "todo"}]}}


def scope(settings=None, survey=SURVEY, guide=GUIDE, zoom=None, size=420, wing=None, rows=ROWS):
    held = {"overlay_mode": "radar"}
    held.update(settings or {})
    over = OV.Overlay(app=App(), tk_module=None, settings=held)
    over.window, over.canvas = Window(size), Canvas()
    over.map_prefs = {"layers": MK.layers(held), "marker_size": held.get("srv_marker_size"),
                      "filter": {"labels": True}}
    over.guidance = guide
    if zoom:
        over.set_zoom(zoom)
    over.draw(rows, 0.0, body="Ega 1", location="2", survey=survey, wing=wing)
    return over


def tagged(over, tag, kind=None):
    return [(name, args, kw) for name, args, kw in over.canvas.calls
            if tag in tuple(kw.get("tags") or ()) and (kind is None or name == kind)]


def texts(over, tag=None):
    return [str(kw.get("text", "")) for name, _a, kw in over.canvas.calls
            if name == "create_text" and (tag is None or tag in tuple(kw.get("tags") or ()))]


@section("the scope follows the map's layer switches")
def _layers():
    plain = scope()
    for tag in ("border", "drive", "ring", "wpnow", "gap", "chevron"):
        check("%s is on the scope as it ships" % tag, tagged(plain, tag), tag)
    for name, tag in (("border", "border"), ("drive", "drive"), ("rings", "ring"),
                      ("waypoints", "wpnow"), ("gaps", "gap"), ("pointer", "chevron")):
        off = scope({MK.setting_of(name): False})
        check("%s switched off: gone from the scope" % name, not tagged(off, tag), tagged(off, tag)[:1])
    off = scope({"map_show_waypoints": False})
    check("with the points hidden the words still say where to go",
          any(t.startswith("WP 2/3") for t in texts(off)), texts(off))


@section("the pointer and you, on the scope")
def _pointer():
    plain = scope()
    kinds = sorted({name for name, _a, _k in tagged(plain, "chevron")})
    check("the pointer is a line with a dot", kinds == ["create_line", "create_oval"], kinds)

    def tall(over):
        points = [args[0] for name, args, kw in tagged(over, "me", "create_polygon")][0]
        ys = [p[1] for p in points]
        return max(ys) - min(ys)
    standard = tall(scope({"srv_marker_size": "standard"}))
    larger = tall(scope({"srv_marker_size": "larger"}))
    largest = tall(scope({"srv_marker_size": "largest"}))
    check("you are drawn at the size set: Standard, Larger, Largest",
          standard < larger < largest, (standard, larger, largest))
    check("left unset, you are Larger", tall(scope()) == larger)


@section("a scale bar on the scope")
def _scale_bar():
    plain = scope()
    line = [args for _n, args, _k in tagged(plain, "scalebar", "create_line")]
    label = texts(plain, "scalebar")
    check("a bar and its length in words", len(line) >= 1 and len(label) == 1, (line, label))

    def per_metre(over):
        bar = [args for _n, args, _k in tagged(over, "scalebar", "create_line")][0]
        words = texts(over, "scalebar")[0]
        metres = float(words.split()[0]) * (1000.0 if words.endswith("km") else 1.0)
        return abs(bar[2] - bar[0]) / metres
    check("the label is a round length", label and label[0] in [PV.scale_text(s) for s in PV.NICE_STEPS_M],
          label)
    one, two = per_metre(plain), per_metre(scope(zoom=2))
    check("and the bar is to the scope's own scale: twice the pixels a metre at 2x",
          abs(two / one - 2.0) < 0.05, (one, two))


@section("centre 4.1 km NE, kept on the scope")
def _centre():
    away = dict(SURVEY, centre=(2900.0, 2900.0))
    far = scope(survey=away, guide=None)
    words = [t for t in texts(far) if t.startswith("CENTRE")]
    check("how far and which way the survey centre is", words and "4.10km NE" in words[0], words)
    near = scope(guide=None)
    words = [t for t in texts(near) if t.startswith("CENTRE")]
    check("standing on it, the header is as it was", words == ["CENTRE  SITE"], words)


@section("the swept ground in km2")
def _swept():
    plain = scope()
    words = [t for t in texts(plain) if t.startswith("SWEPT")]
    check("the share and the area", words == ["SWEPT 83%  2.4 km2"], words)
    none = scope(survey=dict(SURVEY, painted_km2=0))
    check("no area yet, the share alone", [t for t in texts(none) if t.startswith("SWEPT")] == ["SWEPT 83%"])


@section("the keys on the scope, behind a switch")
def _hints():
    wide = scope(size=900, guide=None, survey=None)
    hint = [t for t in texts(wide) if "SITE" in t and "DEPOSIT" in t]
    check("with room: the working keys, the zoom key and the planner's key",
          hint and "ZOOM" in hint[0] and "PLAN" in hint[0] and "Alt+- ZOOM" in hint[0], hint)
    narrow = scope(size=420, guide=None, survey=None)
    old = [t for t in texts(narrow) if "SITE" in t and "DEPOSIT" in t]
    check("with less room the working keys alone, as before",
          old == ["Alt+1 SITE  Alt+2 BORDER  Alt+3 DEPOSIT  Alt+4-9 RIG"] or old == [], old)
    off = scope({"overlay_key_hints": False}, size=900, guide=None, survey=None)
    check("switched off: no keys on the scope",
          not [t for t in texts(off) if "SITE" in t and "DEPOSIT" in t])
    over = OV.Overlay(app=App(), tk_module=None, settings={"overlay_mode": "radar"})
    check("the planner's key and the zoom key in the keys bound",
          over.key_hint(more=True).endswith("PLAN") and "ZOOM" in over.key_hint(more=True)
          and "ZOOM" not in over.key_hint(), over.key_hint(more=True))
    unbound = OV.Overlay(app=App(), tk_module=None,
                         settings={"overlay_mode": "radar", "hotkey_zoom": "", "hotkey_trace": ""})
    check("a key left unbound is left out",
          "ZOOM" not in unbound.key_hint(more=True) and "PLAN" not in unbound.key_hint(more=True))


@section("the zoom step is kept across a restart")
def _zoom_kept():
    held = {"overlay_mode": "radar"}
    over = OV.Overlay(app=App(), tk_module=None, settings=held)
    check("1x to begin with", over.scope_zoom() == 1)
    over.cycle_zoom()
    check("the step is written to the settings", held.get("scope_zoom") == 2, held.get("scope_zoom"))
    again = OV.Overlay(app=App(), tk_module=None, settings=dict(held))
    check("a new start is on the step it was left on", again.scope_zoom() == 2)
    check("nonsense in the file is 1x",
          OV.Overlay(app=App(), tk_module=None, settings={"scope_zoom": "9"}).scope_zoom() == 1)


@section("lines between deposits at 2x and 4x")
def _links():
    on = {"map_show_links": True}
    check("at 1x: none", not tagged(scope(on), "deplink"))
    close = [dict(ROWS[0], range_m=60.0), dict(ROWS[1], range_m=90.0), dict(ROWS[2], range_m=80.0)]
    check("at 1x, however close they are: none", not tagged(scope(on, rows=close), "deplink"))
    two = scope(on, zoom=2, guide=None, survey=None, rows=close)
    check("at 2x: a line from each deposit to its nearest",
          len(tagged(two, "deplink", "create_line")) >= 2, len(tagged(two, "deplink")))
    four = scope(on, zoom=4, guide=None, survey=None, rows=close)
    check("and at 4x", len(tagged(four, "deplink", "create_line")) >= 1, len(tagged(four, "deplink")))
    check("switched off: none at any zoom", not tagged(scope(zoom=4, rows=close), "deplink"))


@section("a wingmate's collected rig on the scope")
def _wing():
    wing = {"mates": [{"name": "CMDR Vee", "east": 100.0, "north": -100.0, "colour": "#c77dff",
                       "rigs": [], "finds": [], "sweep": [],
                       "collected": [{"n": 2, "east": 200.0, "north": -150.0}]}]}
    over = scope(wing=wing, guide=None)
    marks = tagged(over, "wingcollected", "create_rectangle")
    check("kept, dashed", marks and marks[0][2].get("dash"), marks)


@section("skip this pin: which pin is next, and what a skip does")
def _pins():
    pins = [{"n": 1}, {"n": 2}, {"n": 3}]
    check("nothing skipped: the first waiting pin", RP.following_pin(pins, [])["n"] == 1)
    check("one skipped: the one after it", RP.following_pin(pins, [1])["n"] == 2)
    check("no pins waiting: none", RP.following_pin([], [1]) is None)
    skipped, n = RP.skip_pin([], pins)
    check("a skip leaves out the pin being driven to", (skipped, n) == ([1], 1), (skipped, n))
    skipped, n = RP.skip_pin(skipped, pins)
    check("and the next", (skipped, n) == ([1, 2], 2), (skipped, n))
    skipped, n = RP.skip_pin(skipped, pins)
    check("skipping the last one left starts round again", (skipped, n) == ([], 3), (skipped, n))
    check("so there is always a pin to go to", RP.following_pin(pins, skipped)["n"] == 1)
    check("with nothing waiting a skip does nothing", RP.skip_pin([1], []) == ([1], None))


@section("skip this pin is an action like the others: a key and a joystick button")
def _skip_action():
    check("a joystick button can be bound to it", "pin_skip" in IND.JOY_ACTIONS
          and IND.joy_setting("hotkey_pin_skip") == "joy_pin_skip")


@section("chat words: signal, border, zoom, plan rigs, skip pin")
def _chat():
    def action(message):
        found = CT.parse_command(message)
        return found.get("action") if found else None
    check("!rr signal logs the signal", action("!rr signal") == "signal"
          and action("!rr log signal") == "signal")
    check("!rr border sets the border", action("!rr border") == "border")
    check("!rr zoom steps the scope", action("!rr zoom") == "zoom")
    check("!rr plan starts or closes the rig planner's trace",
          action("!rr plan") == "plan" and action("!rr plan rigs") == "plan")
    check("!rr skip skips the pin", action("!rr skip") == "skip_pin"
          and action("!rr skip pin") == "skip_pin")
    check("the old ones still work", action("!rr centre") == "centre" and action("!rr undo") == "undo"
          and action("!rr rig down 3") == "rig_down" and action("!rr alexandrite h/m 4") == "mark")
    check("a commodity is still a commodity", CT.parse_command("!rr platinum h/h 6")["commodity"] == "Platinum")
    check("the help line names them", all(w in CT.HELP for w in ("signal", "border", "zoom", "plan", "skip")),
          CT.HELP)

    class Fake:
        def __init__(self):
            self.ran = []
            self._flashed = False

        def flash_said(self):
            self.ran.append("flash")

        def log_location(self):
            self.ran.append("signal")

        def set_survey_border(self):
            self.ran.append("border")

        def cycle_scope_zoom(self):
            self.ran.append("zoom")

        def trace_key(self):
            self.ran.append("plan")

        def skip_pin(self):
            self.ran.append("skip_pin")
    fake = Fake()
    for word in ("signal", "border", "zoom", "plan", "skip_pin"):
        IM.run_command(fake, {"action": word})
    check("each runs what its key runs", [r for r in fake.ran if r != "flash"]
          == ["signal", "border", "zoom", "plan", "skip_pin"], fake.ran)
    guide = read("docs", "GUIDE.md")
    check("the guide lists the new words", all(("!rr %s" % w) in guide for w in
                                               ("signal", "border", "zoom", "plan", "skip")))
    check("and says local chat is public", "local chat is public" in guide.lower()
          or "local chat is read by everyone" in guide.lower())


# ---------------------------------------------------------------------------
# The app's half: needs the toolkit to import, not a window to open
# ---------------------------------------------------------------------------

HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the app's half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


if HAVE_DISPLAY:
    import edonline as EDO    # noqa: E402

    def _offline(*_args, **_kwargs):
        raise RuntimeError("offline in tests")
    EDO.get_json = _offline
    EDO.post_json = _offline
    OV.foreground_is_game = lambda: None
    import edsmt as A         # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")


@on_screen("the app: settings, the key and the saved zoom")
def _app():
    check("the keys on the scope start on, the zoom step at 1x",
          A.DEFAULT_SETTINGS.get("overlay_key_hints") is True
          and A.DEFAULT_SETTINGS.get("scope_zoom") == 1)
    check("skip this pin has a key and a button of its own, unbound to begin with",
          A.DEFAULT_SETTINGS.get("hotkey_pin_skip") == "" and A.DEFAULT_SETTINGS.get("joy_pin_skip") == "")
    check("bound, it is registered with the others",
          A.EDSMT.wanted_hotkeys(dict(A.DEFAULT_SETTINGS, hotkey_pin_skip="ALT+P")).get("pin_skip")
          == "ALT+P")
    check("unbound, it is not", "pin_skip" not in A.EDSMT.wanted_hotkeys(dict(A.DEFAULT_SETTINGS)))
    check("each has its note in Settings", all(k in A.SETTING_TIPS for k in
                                               ("overlay_key_hints", "hotkey_pin_skip")),
          [k for k in ("overlay_key_hints", "hotkey_pin_skip") if k not in A.SETTING_TIPS])
    source = read("edsmt.py")
    check("Settings > Keys has its row, and Overlay the switch",
          '"hotkey_pin_skip", "Rig planner: skip this pin"' in source
          and 'self._switch(body, "overlay_key_hints"' in source)

    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    said, saved, flashed = [], [], []
    app.say = lambda text, colour=None: said.append(str(text)) or True
    app.flash = lambda *args, **kw: flashed.append(args)
    app.redraw = lambda: None
    real_save = A.save_settings
    A.save_settings = lambda data: saved.append(dict(data)) or True
    try:
        app.overlay = OV.Overlay(app=App(), tk_module=None, settings=app.settings)
        app.cycle_scope_zoom()
        check("the zoom key saves the step it lands on",
              saved and saved[-1].get("scope_zoom") == 2, saved[-1].get("scope_zoom") if saved else None)
    finally:
        A.save_settings = real_save

    # Skip this pin, through the planner's own marks.
    pins = [{"n": n, "east": 80.0 * n, "north": 0.0, "done": False, "mine": True,
             "range_m": 80.0 * n} for n in (1, 2, 3)]
    plan = {"system": "sys", "body": "body", "pins": [{"n": n, "lat": 0.0, "lon": 0.001 * n}
                                                      for n in (1, 2, 3)]}
    check("the pins left out are kept for this plan only",
          app.pin_skips(plan) == [] and app.pin_skips(None) == [])
    app.plan_marks = lambda: {"tracing": False, "pins": pins, "next": RP.following_pin(
        pins, app.pin_skips(plan))["n"], "plan": plan}
    app.speak = lambda *a, **k: None
    del said[:]
    check("skip: pin 1 is left out and pin 2 is next", app.skip_pin() is True
          and app.pin_skips(plan) == [1] and "P1" in said[-1] and "P2" in said[-1], said)
    app.skip_pin()
    app.skip_pin()
    check("round to the first again when every one has been skipped",
          app.pin_skips(plan) == [] and "P1" in said[-1], (app.pin_skips(plan), said[-1]))
    other = dict(plan, pins=[{"n": 1, "lat": 5.0, "lon": 5.0}])
    app.skip_pin()
    check("another plan starts with none left out", app.pin_skips(other) == [])
    app.plan_marks = lambda: None
    del said[:]
    check("with no plan up it says so", app.skip_pin() is False and "no rig plan" in said[-1].lower(), said)
    check("the key's table runs it", '"pin_skip": ("Rig planner", self.skip_pin)' in source
          or 'table["pin_skip"] = ("Rig planner", self.skip_pin)' in source)
    check("and the planner follows the pins not skipped",
          "RP.following_pin(" in source and "self.pin_skips(" in source)


print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
