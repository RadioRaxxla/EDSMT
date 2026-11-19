"""1.10042: the map explained, and every layer of it switchable.

A tester's two pictures of the map (12 Nov): "What are all these small
circles?", "What are these circles? ... Ditto the dashed lines", "What is
this arrow?", "Waypt added by mistake. How can it be removed?", "My location
is most important. This arrow should be white and slightly larger", and a
rig set just outside the deposit that could not be removed while "Clear
planning circle" did nothing. Now:

  - a key names every mark in plain words: the "?" on the map, the map's
    right-click menu, Help, and the welcome's "How to customise the map";
  - a switch for each layer - survey border, circles to drive, range rings,
    guided-survey points, gaps, the waypoint pointer, the new lines between
    deposits - on the right-click menu and in Settings, kept in settings,
    starting where the map has always been;
  - the waypoint pointer is a line with a dot, in its own colour; you are a
    white arrow, a little larger, with a size setting;
  - right-click on or near a waypoint: remove it, or skip it; on or near a
    rig: pick it up, or change its commodity, with a bigger reach than the
    old 12-pixel square; "Clear the planning circle" only when there is one;
  - waypoint 1 is LANDED (where you touched down), said once, removable;
  - a wingmate's collected rig stays on the map, marked collected;
  - zoomed in, lines from deposit to deposit with their lengths.

The first half is plain functions and needs no display. The second half
opens the window on the real toolkit and says SKIP, out loud, without one.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_mapkey.py
"""
import faulthandler
import io
import json
import math
import os
import re
import sys
import tempfile
import time

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-key42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import planview as PV     # noqa: E402
import waypoints as WP    # noqa: E402
import wingmates as WM    # noqa: E402

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


try:
    import mapkey as MK   # noqa: E402
except ImportError as _exc:
    MK = None
    print("== the map key ==")
    check("mapkey.py is there to import", False, _exc)


# ---------------------------------------------------------------------------
# (i) Plain functions
# ---------------------------------------------------------------------------

@section("the layers: one switch each, starting where the map has always been")
def _layers():
    names = [name for _k, name, _l, _d in MK.LAYERS]
    check("border, circles to drive, range rings, waypoints, gaps, pointer, links",
          names == ["border", "drive", "rings", "waypoints", "gaps", "pointer", "links"], names)
    check("each kept in settings under a name of its own",
          all(MK.setting_of(n).startswith("map_show_") for n in names)
          and len({MK.setting_of(n) for n in names}) == len(names))
    check("as it ships, everything that was drawn is still drawn; the new lines are off",
          MK.layers({}) == {"border": True, "drive": True, "rings": True, "waypoints": True,
                            "gaps": True, "pointer": True, "links": False}, MK.layers({}))
    check("a switch turned off is off", MK.layers({"map_show_rings": False})["rings"] is False
          and MK.layers({"map_show_links": True})["links"] is True)
    prefs = {"layers": MK.layers({"map_show_gaps": False})}
    check("the map is asked through its preferences", MK.shown(prefs, "gaps") is False
          and MK.shown(prefs, "border") is True)
    check("with no preferences at all, today's look", MK.shown({}, "border") is True
          and MK.shown(None, "pointer") is True and MK.shown({}, "links") is False)
    check("every switch has its note for Settings", set(MK.TIPS) == set(MK.SETTINGS), sorted(MK.TIPS))


@section("the key: every mark named in plain words")
def _key():
    text = "\n".join("%s: %s" % (name, words) for name, words, _s in MK.key_lines()) \
        + "\n" + MK.WHERE_SWITCHES
    low = text.lower()
    for words in ("where to press your mineral scanner if you don't hold it down all the time",
                  "survey border", "circles to drive", "range rings", "gap",
                  "waypoint", "landed", "your marker", "rig", "spacing rings",
                  "planning circle", "collected"):
        check("names %r" % words, words in low, text[:200])
    check("the pointer is said not to be you", "it is not you" in low)
    check("LANDED is where you touched down, and the ship may have left",
          "where you touched down" in low and "ship may have left" in low)
    check("the planning circle is said not to be a rig", "it is not a rig" in low)
    check("and it says where the switches are", "right-click the map" in low
          and "settings > overlay > map and scope" in low)
    lines = MK.key_lines({"layers": MK.layers({"map_show_rings": False})})
    rings = [state for name, _w, state in lines if name == "Range rings"]
    check("a mark switched off is said to be off", rings == ["off"], rings)
    check("one with no switch says nothing about one",
          [s for n, _w, s in lines if n == "Deposits"] == [""])


@section("your marker: white, a little larger, its size a setting")
def _marker():
    check("white unless another colour is picked", MK.MARKER_WHITE == "#ffffff")
    check("three sizes, Larger for a new install",
          [k for _l, k, _s in MK.MARKER_SIZES] == ["standard", "larger", "largest"]
          and MK.MARKER_SIZE_DEFAULT == "larger")
    check("standard is the old 12 on the map", MK.marker_size("standard", 12) == 12)
    check("larger is a quarter bigger", MK.marker_size("larger", 12) == 15)
    check("by its name or its key", MK.marker_size("Largest", 11) == MK.marker_size("largest", 11) > 15)
    check("nonsense is the default", MK.marker_size("huge", 12) == MK.marker_size("larger", 12))


@section("what a right-click is near: the nearest mark within reach")
def _near():
    marks = [(100, 100, "a"), (130, 100, "b"), (400, 400, "c")]
    check("on a mark", PV.near_mark(marks, 101, 99) == "a")
    check("near it - the reach is wider than the old 12-pixel square",
          PV.near_mark(marks, 100, 114) == "a" and PV.NEAR_PX >= 16, PV.NEAR_PX)
    check("the nearer of two", PV.near_mark(marks, 120, 100) == "b")
    check("nothing within reach is nothing", PV.near_mark(marks, 250, 250) is None)
    check("no marks, nothing", PV.near_mark([], 1, 1) is None and PV.near_mark(None, 1, 1) is None)
    check("a reach can be asked for", PV.near_mark(marks, 300, 300, reach=150) == "c")


@section("the pointer: a line with a dot, not a second you")
def _pointer():
    shape = PV.pointer_shape(200, 200, 90.0)
    x1, y1, x2, y2 = shape["line"]
    check("a line out from beside you along the bearing (east)",
          x2 > x1 > 200 and abs(y1 - 200) < 0.01 and abs(y2 - 200) < 0.01, shape)
    dx0, dy0, dx1, dy1 = shape["dot"]
    check("with a dot at its far end", abs((dx0 + dx1) / 2 - x2) < 0.01
          and abs((dy0 + dy1) / 2 - y2) < 0.01 and dx1 - dx0 >= 5, shape)
    north = PV.pointer_shape(200, 200, 0.0)
    check("north is up", north["line"][3] < north["line"][1] < 200, north)
    check("and it never starts on you", math.hypot(x1 - 200, y1 - 200) >= 12)


@section("lines between deposits: each to its nearest, with the length")
def _links():
    def item(i, east, north, amount="High", off=False):
        return {"id": str(i), "east_m": east, "north_m": north, "x": east, "y": -north,
                "offscreen": off, "commodity": "Iridium",
                "deposit": {"id": str(i), "amount": amount}}
    items = [item(1, 0, 0), item(2, 300, 0), item(3, 300, 400), item(4, 2000, 0),
             item(5, 2100, 0, amount="Depleted"), item(6, 9000, 0, off=True)]
    links = PV.deposit_links(items)
    pairs = sorted(tuple(sorted((l["a"]["id"], l["b"]["id"]))) for l in links)
    check("each live deposit on screen joined to its nearest, once a pair",
          pairs == [("1", "2"), ("2", "3"), ("2", "4")], pairs)
    lengths = sorted(round(l["range_m"]) for l in links)
    check("with the length of each", lengths == [300, 400, 1700], lengths)
    check("a mined-out deposit and one off the edge have none",
          not any(l["a"]["id"] in ("5", "6") or l["b"]["id"] in ("5", "6") for l in links))
    check("never more than asked", len(PV.deposit_links(items, most=1)) == 1)
    check("one deposit, no lines", PV.deposit_links(items[:1]) == [])
    check("zoomed in on the map: closer than the fitted view, or under 1.5 km",
          PV.links_wanted(800.0, 2000.0) and PV.links_wanted(1500.0, 1500.0)
          and not PV.links_wanted(3000.0, 3000.0))
    check("on the scope: at 2x and 4x", PV.links_wanted(5000.0, 5000.0, zoom=2)
          and PV.links_wanted(5000.0, 5000.0, zoom=4) and not PV.links_wanted(5000.0, 5000.0, zoom=1))


@section("a scale bar: a round length that fits")
def _scale():
    found = PV.scale_bar(10.0, 80)      # 10 m a pixel, 80 px of room
    check("the longest round length that fits", found == (500, 50.0), found)
    check("its label", PV.scale_text(500) == "500 m" and PV.scale_text(2000) == "2 km"
          and PV.scale_text(2500) == "2.5 km", (PV.scale_text(2000), PV.scale_text(2500)))
    check("no room, no bar", PV.scale_bar(10.0, 5) is None and PV.scale_bar(0, 80) is None)


@section("waypoint 1 is LANDED, and any waypoint can be removed")
def _waypoints():
    points = [{"n": n, "lat": 0.0, "lon": n * 0.01, "ring": 0 if n == 1 else 1,
               "radius_m": 0.0 if n == 1 else 2000.0, "bearing": 0.0} for n in range(1, 7)]
    guide = WP.Guide("Sys", "Body 1", (1, 2, 3, 4, 5), [dict(p) for p in points])
    check("the first, at the centre, is where you landed",
          WP.is_landed(guide.waypoints[0]) and not WP.is_landed(guide.waypoints[1])
          and guide.landed() is guide.waypoints[0])
    check("not said yet", guide.landed_said is False)
    guide.skip()
    guide.advance()
    check("on WP 3 with WP 1 skipped", guide.current()["n"] == 3 and guide.skipped == [1])
    check("removing WP 1 takes it out", guide.remove(1) is True and guide.total == 5)
    check("the rest are numbered on from 1, and the one being driven to stays it",
          [p["n"] for p in guide.waypoints] == [1, 2, 3, 4, 5] and guide.current()["n"] == 2
          and guide.label() == "WP 2/5", (guide.label(), [p["n"] for p in guide.waypoints]))
    check("a removed waypoint is not counted as skipped", guide.skipped == [], guide.skipped)
    check("and with it gone there is no LANDED", guide.landed() is None)
    check("removing the one being driven to moves on to the next",
          guide.remove(2) and guide.current()["n"] == 2 and guide.total == 4
          and guide.current()["lon"] == points[3]["lon"], guide.current())
    check("one that is not there is not removed", guide.remove(99) is False and guide.total == 4)
    guide.remove(4)
    guide.remove(3)
    check("with the ones after it gone, it is the last", guide.current()["n"] == 2
          and guide.total == 2)
    check("and removing it finishes the survey",
          guide.remove(2) and guide.done and guide.current() is None and guide.total == 1)
    kept = WP.Guide("Sys", "Body 1", (1,), [dict(p) for p in points])
    kept.landed_said = True
    again = WP.Guide.from_dict(json.loads(json.dumps(kept.to_dict())))
    check("said once: kept on disk with the guide", again.landed_said is True)
    check("and a file from before keeps working", WP.Guide.from_dict(
        {k: v for k, v in kept.to_dict().items() if k != "landed_said"}).landed_said is False)


@section("a wingmate's collected rig stays, marked collected")
def _collected():
    place = ("Sys", "Body 1")
    mates = [{"name": "CMDR Vee", "rigs": [{"n": 1, "lat": 1.0, "lon": 2.0},
                                           {"n": 2, "lat": 1.001, "lon": 2.0}]}]
    kept, shown = WM.keep_collected(None, place, mates)
    check("first look: both rigs, nothing collected",
          len(shown[0]["rigs"]) == 2 and shown[0]["collected"] == [], shown)
    later = [{"name": "Vee", "rigs": [{"n": 2, "lat": 1.001, "lon": 2.0}]}]
    kept, shown = WM.keep_collected(kept, place, later)
    check("rig 1 picked up: kept, marked collected",
          [r["n"] for r in shown[0]["collected"]] == [1] and len(shown[0]["rigs"]) == 1, shown)
    kept, shown = WM.keep_collected(kept, place, later)
    check("and it stays on the next look", [r["n"] for r in shown[0]["collected"]] == [1])
    back = [{"name": "Vee", "rigs": [{"n": 2, "lat": 1.001, "lon": 2.0},
                                     {"n": 1, "lat": 1.0, "lon": 2.0}]}]
    kept, shown = WM.keep_collected(kept, place, back)
    check("put down again in the same spot, it is a rig again", shown[0]["collected"] == []
          and len(shown[0]["rigs"]) == 2, shown)
    kept, shown = WM.keep_collected(kept, place, [{"name": "Vee", "rigs": []}])
    kept, shown = WM.keep_collected(kept, ("Sys", "Body 2"), [{"name": "Vee", "rigs": []}])
    check("leaving the planet forgets them, as the game does", shown[0]["collected"] == [], shown)
    many = [{"name": "Vee", "rigs": [{"n": n % 6 + 1, "lat": n * 0.01, "lon": 0.0}
                                     for n in range(30)]}]
    kept, _ = WM.keep_collected(None, place, many)
    kept, shown = WM.keep_collected(kept, place, [{"name": "Vee", "rigs": []}])
    check("never more than a dozen kept for one wingmate", len(shown[0]["collected"]) <= 12,
          len(shown[0]["collected"]))
    check("junk is no rigs, not a fault", WM.keep_collected({"x": 1}, place, [{"name": "Vee", "rigs": [{"n": 1}]}])[1][0]["collected"] == [])


@section("none of the plain half touches a widget")
def _plain():
    for name in ("mapkey.py", "planview.py", "waypoints.py", "wingmates.py"):
        check("%s knows nothing of the toolkit" % name, "tkinter" not in read(name))


# ---------------------------------------------------------------------------
# (ii) On the real toolkit
# ---------------------------------------------------------------------------

HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the window half of this file - no display (%s). "
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
    import overlay as OV      # noqa: E402
    OV.foreground_is_game = lambda: None
    import voice as VO        # noqa: E402
    import edsmt as A         # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION,
                   "tour_done": True, "journal_dir": JOURNALS,
                   "overlay_enabled": False}, _f)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None
    trouble = []
    app.report_callback_exception = lambda *args: trouble.append(args)

    def pump(seconds=0.15):
        until = time.time() + seconds
        while True:
            app.update_idletasks()
            app.update()
            if time.time() >= until:
                break
            time.sleep(0.01)

    def settle_until(cond, seconds=10.0):
        until = time.time() + seconds
        while time.time() < until:
            if cond():
                return True
            pump(0.03)
        return bool(cond())

    pump(0.5)
    asked = []
    holder = tkinter.Toplevel(app)
    holder.geometry("900x700+20+20")
    plan = A.PlanView(holder, on_menu=lambda action, payload: asked.append((action, payload)))
    plan.pack(fill="both", expand=True)
    settle_until(lambda: plan.winfo_width() > 500)

    def rows_near(*places):
        out = []
        for n, (east, north, what) in enumerate(places, 1):
            out.append({"range_m": math.hypot(east, north),
                        "bearing": math.degrees(math.atan2(east, north)) % 360,
                        "deposit": {"id": "d%d" % n, "commodity": what, "amount": "High",
                                    "density": "High", "rigs": "2"}})
        return out

    ROWS = rows_near((300, 200, "Iridium"), (420, 250, "Iridium"), (-350, 380, "Painite"))
    SURVEY = {"centre": (0.0, 0.0), "border_m": 1500.0, "rings": [500.0, 1000.0],
              "gaps": [{"east": 900.0, "north": -300.0, "area_km2": 0.4}],
              "points": [], "scan_m": 500.0, "percent": 40}
    GUIDE = {"wp": {"complete": False, "text": "WP 2/3: 849 m, bearing 045",
                    "bearing": 45.0, "range_m": 849.0, "n": 2, "total": 3,
                    "arrive_m": 250.0,
                    "points": [{"n": 1, "east": 0.0, "north": 0.0, "state": "done",
                                "landed": True},
                               {"n": 2, "east": 600.0, "north": 600.0, "state": "current"},
                               {"n": 3, "east": -600.0, "north": -700.0, "state": "todo"}]}}
    RIGS = {"rigs": [{"n": 1, "label": "1", "east": -300.0, "north": -300.0,
                      "range_m": 424.0, "commodity": "Iridium"}], "limit_m": 4500.0}

    def draw(settings=None, guide=GUIDE, extent=None):
        prefs = app.map_prefs(prices=False)
        prefs["layers"] = MK.layers(settings or {})
        prefs["marker_size"] = (settings or {}).get("srv_marker_size", "larger")
        plan.map_prefs = prefs
        plan.marker = OV.marker_colour({"srv_colour": "#ffffff"})
        plan.guidance = guide
        plan._extent = extent
        plan.show(ROWS, heading=0.0, caption="x", survey=SURVEY, rigs=RIGS, signal="1")
        pump(0.05)

    def tags_of(canvas):
        out = {}
        for item in canvas.find_all():
            for tag in canvas.gettags(item):
                out[tag] = out.get(tag, 0) + 1
        return out

    def texts(canvas, tag=None):
        found = canvas.find_withtag(tag) if tag else canvas.find_all()
        return [canvas.itemcget(i, "text") for i in found if canvas.type(i) == "text"]


@on_screen("Settings: a switch for every layer, and you white and Larger")
def _settings():
    check("every layer's switch is a setting with its default",
          all(A.DEFAULT_SETTINGS.get(k) == v for k, v in MK.SETTINGS.items()),
          {k: A.DEFAULT_SETTINGS.get(k) for k in MK.SETTINGS})
    check("you are white on a new install", A.DEFAULT_SETTINGS.get("srv_colour") == "#ffffff")
    check("and Larger", A.DEFAULT_SETTINGS.get("srv_marker_size") == "larger")
    check("a file from before 1.10042 on the theme's own colour turns white",
          A.upgrade_marker({"srv_colour": ""}, {"srv_colour": ""})["srv_colour"] == "#ffffff")
    check("a colour somebody picked is kept",
          A.upgrade_marker({"srv_colour": "#ff00aa"}, {"srv_colour": "#ff00aa"})["srv_colour"]
          == "#ff00aa")
    check("and the theme's own chosen again after it stays chosen",
          A.upgrade_marker({"srv_colour": ""},
                           {"srv_colour": "", "srv_marker_size": "larger"})["srv_colour"] == "")
    check("every new setting has its note", all(k in A.SETTING_TIPS for k in
                                                list(MK.SETTINGS) + ["srv_marker_size"]))
    prefs = app.map_prefs()
    check("the map and the scope are handed the layers and your size",
          prefs.get("layers") == MK.layers(app.settings)
          and prefs.get("marker_size") == app.settings.get("srv_marker_size"), prefs.get("layers"))
    window = A.SettingsWindow(app)
    pump(0.3)
    check("Settings > Overlay > Map and scope has a switch for each",
          all(k in window.toggles for k in MK.SETTINGS), sorted(k for k in MK.SETTINGS
                                                                 if k not in window.toggles))
    check("and the size of your marker", "srv_marker_size" in getattr(window, "choices", {}),
          sorted(getattr(window, "choices", {}))[:40])
    window.destroy()
    pump(0.1)


@on_screen("the map: each layer drawn, and gone when its switch is off")
def _layers_drawn():
    draw()
    tags = tags_of(plan)
    for tag in ("border", "drive", "ring", "wpnow", "wpnext", "gap", "chevron"):
        check("%s is drawn as it ships" % tag, tags.get(tag, 0) >= 1, sorted(tags))
    check("the lines between deposits are not, until switched on", not tags.get("deplink"))
    for name, tag in (("border", "border"), ("drive", "drive"), ("rings", "ring"),
                      ("waypoints", "wpnow"), ("gaps", "gap"), ("pointer", "chevron")):
        draw({MK.setting_of(name): False})
        check("%s switched off: gone from the map" % name, not tags_of(plan).get(tag),
              tags_of(plan).get(tag))
    draw({"map_show_rings": False})
    check("and nothing else goes with it", tags_of(plan).get("border") and tags_of(plan).get("wpnow"))
    draw({"map_show_waypoints": False})
    check("with the points hidden the guided survey still says where to go",
          any(t.startswith("WP 2/3") for t in texts(plan, "wptext")), texts(plan, "wptext"))
    draw({"map_show_links": True})
    check("switched on but the map not zoomed in: still no lines",
          not tags_of(plan).get("deplink") or plan.last_viewport.extent_m <= PV.LINK_VIEW_M,
          plan.last_viewport.extent_m)
    draw({"map_show_links": True}, extent=900.0)
    lengths = texts(plan, "deplinklabel")
    check("zoomed in: a line from each deposit to its nearest, with its length",
          tags_of(plan).get("deplink", 0) >= 2 and any(t.endswith(" m") for t in lengths),
          (tags_of(plan).get("deplink"), lengths))
    draw()


@on_screen("the pointer is a line with a dot; you are a white arrow, a little larger")
def _pointer_drawn():
    draw()
    kinds = sorted({plan.type(i) for i in plan.find_withtag("chevron")})
    check("the waypoint pointer is a line and a dot, not an arrow like yours",
          kinds == ["line", "oval"], kinds)
    me = plan.find_withtag("me")
    fills = {plan.itemcget(i, "fill") for i in me}
    check("you are white", fills == {"#ffffff"}, fills)
    pointer = {plan.itemcget(i, "fill") for i in plan.find_withtag("chevron")} - {""}
    check("and the pointer is not your colour", pointer and "#ffffff" not in pointer, pointer)

    def height():
        box = plan.bbox(plan.find_withtag("me")[0])
        return box[3] - box[1]
    larger = height()
    draw({"srv_marker_size": "standard"})
    standard = height()
    draw({"srv_marker_size": "largest"})
    largest = height()
    check("Larger is bigger than the old size, Largest bigger again",
          standard < larger < largest, (standard, larger, largest))
    draw()


@on_screen("waypoint 1 is LANDED on the map")
def _landed_drawn():
    draw()
    check("labelled LANDED", "LANDED" in texts(plan, "wplanded"), texts(plan, "wplanded"))
    check("the next is still WP 2", "WP 2" in texts(plan, "wplabel"), texts(plan, "wplabel"))


def menu_entries(menu):
    out = []
    for i in range((menu.index("end") or -1) + 1):
        kind = menu.type(i)
        if kind in ("command", "checkbutton"):
            out.append((kind, menu.entrycget(i, "label")))
    return out


def menu_at(x, y):
    plan._menu_at = (x, y)
    return plan.context_menu()


@on_screen("right-click: what is near you, and the planning circle only when there is one")
def _menu():
    draw()
    viewport = plan.last_viewport
    empty = viewport.to_canvas(-1200.0, 1200.0)
    menu = menu_at(*empty)
    labels = [label for kind, label in menu_entries(menu) if kind == "command"]
    check("on open ground: Recentre, Planning circle here, the key",
          labels == ["Recentre", "Planning circle here (4.5 km)", "Map key - what every mark is"],
          labels)
    switches = [label for kind, label in menu_entries(menu) if kind == "checkbutton"]
    check("and a switch for every layer", switches == [label for _k, _n, label, _d in MK.LAYERS],
          switches)
    menu.destroy()
    plan.planning_ring = (500.0, 500.0)
    menu = menu_at(*empty)
    labels = [label for kind, label in menu_entries(menu) if kind == "command"]
    check("with a planning circle down: Clear the planning circle, said not to be a rig",
          "Clear the planning circle (not a rig)" in labels, labels)
    menu.destroy()
    plan.planning_ring = None
    wx, wy = viewport.to_canvas(600.0, 600.0)
    menu = menu_at(wx + 8, wy + 6)
    labels = [label for kind, label in menu_entries(menu) if kind == "command"]
    check("near the waypoint being driven to: remove it, or skip it",
          labels[:2] == ["Waypoint 2: remove it", "Waypoint 2: skip it"], labels)
    menu.destroy()
    tx, ty = viewport.to_canvas(-600.0, -700.0)
    menu = menu_at(tx - 10, ty)
    labels = [label for kind, label in menu_entries(menu) if kind == "command"]
    check("near one further on: remove it (skip is for the one being driven to)",
          labels[0] == "Waypoint 3: remove it" and not any("skip" in l for l in labels), labels)
    menu.destroy()
    lx, ly = viewport.to_canvas(0.0, 0.0)
    menu = menu_at(lx + 4, ly + 4)
    labels = [label for kind, label in menu_entries(menu) if kind == "command"]
    check("on LANDED: it can be removed", labels[0] == "LANDED (waypoint 1): remove it", labels)
    menu.destroy()
    rx, ry = viewport.to_canvas(-300.0, -300.0)
    menu = menu_at(rx + 13, ry - 4)
    labels = [label for kind, label in menu_entries(menu) if kind == "command"]
    check("13 px from a rig - outside the old square - pick it up or change it",
          labels[:2] == ["Rig 1: pick it up", "Rig 1: change commodity"], labels)
    del asked[:]
    for i in range(menu.index("end") + 1):
        if menu.type(i) == "command" and menu.entrycget(i, "label").startswith("Rig 1"):
            menu.invoke(i)
    check("each one asks the app for it, with the rig",
          [a for a, _p in asked] == ["rig_up", "rig_commodity"]
          and all(p.get("n") == 1 for _a, p in asked), asked)
    menu.destroy()
    menu = menu_at(wx, wy)
    del asked[:]
    for i in range(menu.index("end") + 1):
        if menu.type(i) == "command" and menu.entrycget(i, "label").startswith("Waypoint 2"):
            menu.invoke(i)
    check("and the waypoint ones, with its number", asked == [("wp_remove", 2), ("wp_skip", 2)],
          asked)
    del asked[:]
    for i in range(menu.index("end") + 1):
        if menu.type(i) == "checkbutton" and menu.entrycget(i, "label") == "Range rings":
            menu.invoke(i)
    check("a layer's switch says which, and that it is now off", asked == [("layer", ("rings", False))],
          asked)
    menu.destroy()


@on_screen("the ? on the map opens the key")
def _key_button():
    draw()
    found = plan.find_withtag("keybutton")
    check("there is a ? on the map", found and "?" in texts(plan, "keybutton"), texts(plan, "keybutton"))
    box = plan.bbox(found[0])
    del asked[:]

    class Click:
        x = (box[0] + box[2]) / 2.0
        y = (box[1] + box[3]) / 2.0
    plan._clicked(Click())
    check("a click on it asks for the key", asked == [("key", None)], asked)


def attr_window():
    found = getattr(app, "map_key_window", None)
    try:
        return found if found is not None and found.winfo_exists() else None
    except Exception:
        return None


def label_texts(widget):
    out = []
    for child in widget.winfo_children():
        try:
            out.append(str(child.cget("text")))
        except Exception:
            pass
        out.extend(label_texts(child))
    return out


@on_screen("the app does what the map asks")
def _app_actions():
    saved = []
    real_save = A.save_settings
    A.save_settings = lambda data: saved.append(dict(data)) or True
    try:
        app.map_menu("layer", ("rings", False))
        check("a layer switched off is kept in settings, and saved",
              app.settings.get("map_show_rings") is False and saved
              and saved[-1].get("map_show_rings") is False)
        app.map_menu("layer", ("rings", True))
        check("and back on", app.settings.get("map_show_rings") is True)
    finally:
        A.save_settings = real_save
    got = []
    real = (app.rig_for, app.pick_up_rig, app.edit_rig)
    app.rig_for = lambda label: {"n": int(label), "label": str(label)}
    app.pick_up_rig = lambda rig: got.append(("up", rig["n"])) or True
    app.edit_rig = lambda mark: got.append(("edit", mark["n"]))
    try:
        app.map_menu("rig_up", {"n": 1, "label": "1"})
        app.map_menu("rig_commodity", {"n": 1, "label": "1"})
    finally:
        app.rig_for, app.pick_up_rig, app.edit_rig = real
    check("pick it up and change commodity reach the rig", got == [("up", 1), ("edit", 1)], got)
    points = [{"n": n, "lat": 0.0, "lon": n * 0.01, "ring": 0 if n == 1 else 1,
               "radius_m": 0.0 if n == 1 else 2000.0, "bearing": 0.0} for n in range(1, 5)]
    guide = WP.Guide("Sys", "Body", (1, 2, 3, 4, 5), points)
    app.waypoint_book.put(guide)
    app._wp_key_guide = lambda: guide
    try:
        app.map_menu("wp_remove", 1)
        check("Remove takes the waypoint out, and the survey says so",
              guide.total == 3 and guide.landed() is None
              and "removed" in app.status.cget("text"), (guide.total, app.status.cget("text")))
        app.map_menu("wp_skip", 1)
        check("Skip skips the one being driven to", guide.skipped == [1], guide.skipped)
    finally:
        del app._wp_key_guide
    app.map_menu("key", None)
    window = attr_window()
    check("the key opens in a window of its own", window is not None)
    if window is not None:
        words = " ".join(label_texts(window))
        missing = [name for name, _w, _l in MK.KEY if name not in words]
        check("naming every mark", not missing, missing)
        check("and saying where the switches are", MK.WHERE_SWITCHES[:30] in words)
        check("with a switch for every layer on it", all(k in window.toggles for k in MK.SETTINGS),
              sorted(window.toggles))
        window.toggles["map_show_gaps"].set(False)
        window.switched("map_show_gaps")
        check("a switch there changes the map's setting", app.settings.get("map_show_gaps") is False)
        window.toggles["map_show_gaps"].set(True)
        window.switched("map_show_gaps")
        app.map_menu("key", None)
        check("asked again, the same window comes forward", attr_window() is window)
        window.destroy()
    check("nothing was raised into the window", not trouble, trouble)


def all_widgets(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(all_widgets(child))
    return out


@on_screen("Help and the welcome: how to customise the map")
def _help():
    labels = [app.help_menu.entrycget(i, "label") for i in range(app.help_menu.index("end") + 1)
              if app.help_menu.type(i) == "command"]
    check("Help has the map key", "Map key - how to customise the map" in labels, labels)
    app.show_welcome(force=True)
    pump(0.5)
    welcome = [w for w in app.winfo_children() if isinstance(w, A.WelcomeWindow)]
    words = " ".join(label_texts(welcome[0])) if welcome else ""
    check("the welcome has a page on customising the map", MK.TITLE.upper() in words.upper(),
          words[:300])
    check("saying where the switches are", "Right-click the map" in words)
    buttons = [b for b in all_widgets(welcome[0]) if isinstance(b, A.ctk.CTkButton)
               and b.cget("text") == "Map key and switches"] if welcome else []
    check("with a button that opens the key", len(buttons) == 1)
    if buttons:
        buttons[0].invoke()
        pump(0.5)
        check("which it does", attr_window() is not None)
        if attr_window() is not None:
            attr_window().destroy()
    for w in app.winfo_children():
        if isinstance(w, A.WelcomeWindow):
            w.destroy()
    if getattr(app, "touring", None) is not None:
        try:
            app.touring.finish()
        except Exception:
            pass
    pump(0.2)


@on_screen("LANDED: said once, in words and by voice")
def _landed_said():
    points = [{"n": n, "lat": 0.0, "lon": n * 0.01, "ring": 0 if n == 1 else 1,
               "radius_m": 0.0 if n == 1 else 2000.0, "bearing": 0.0} for n in range(1, 4)]
    guide = WP.Guide("Sys", "Body", (9, 9, 9, 9, 9), points)
    app.waypoint_book.put(guide)
    heard = []

    class Ear:
        folders = []

        def set_rate(self, rate):
            pass

        def say_line(self, line_id, theme=None, place=None, detail=None):
            heard.append(line_id)
            return True

        def problem(self, since=None):
            return ""
    real_voice = app.voice
    app.voice = Ear()
    app.settings["voice_mode"] = True
    try:
        check("told the first time", app.wp_tell_landed(guide) is True)
        check("by voice, the recorded line (1.2)", heard == ["landed_marked"], heard)
        check("and in words", "where you touched down" in app.status.cget("text"),
              app.status.cget("text"))
        check("never again for this survey", app.wp_tell_landed(guide) is False and heard == ["landed_marked"])
        check("kept with the guide", guide.landed_said is True)
    finally:
        app.voice = real_voice
        app.settings["voice_mode"] = False
    check("1.2: a line of the Basic pack, recorded in every voice",
          "landed_marked" in VO.LINES and "wp_landed" not in VO.SPOKEN_ONLY
          and VO.line_text("landed_marked", "ship_computer") == "Touchdown. Waypoint one marked.")


@on_screen("a wingmate's collected rig stays on the map, marked collected")
def _wing_collected():
    draw()
    plan.wing = {"mates": [{"name": "CMDR Vee", "east": 100.0, "north": -100.0,
                            "colour": "#c77dff", "rigs": [], "finds": [], "sweep": [],
                            "collected": [{"n": 2, "east": 200.0, "north": -150.0}]}]}
    plan.redraw()
    pump(0.05)
    check("drawn, dashed, and named collected", plan.find_withtag("wingcollected")
          and "collected" in " ".join(texts(plan, "wingcollected")), texts(plan, "wingcollected"))
    plan.wing = None
    plan.redraw()
    words = [str(A.SETTING_TIPS.get(k, "")) for k in ("wing_auto", "wing_link")]
    check("the wing's notes say they stay in the game until you leave the planet",
          all("until you leave the planet" in w for w in words), words)
    check("and so does the guide", "until you leave the planet" in read("docs", "GUIDE.md"))

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
