"""1.10042: the tour's card stays in the window, clear of what it names.

Pictures of the real tour (13 Nov) showed three faults: for a wide control -
the map, the tab strip - the card left the app window and sat on the desktop
beside it; at the keys step it covered BORDER, RIGS DOWN and RIGS UP, the
very buttons its words name; and ringing the tab strip pushed everything
under it down by six pixels while the step showed. With them, the words had
not kept up: Settings was described as it was three versions ago, and the
status strip, the shortcut bar and Help had no step.

Now the card is placed against the app window first and the screen second,
never over the control or the buttons the step names where there is room
beside them; the ring is drawn over the window and takes no room in its
layout; and the steps say what is there now.

The placing is a plain function and needs no display. The second half opens
the tour on the real toolkit and says SKIP, out loud, without one.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_tour.py
"""
import faulthandler
import io
import json
import os
import sys
import tempfile
import time

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-tour42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import welcome as WL      # noqa: E402

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


def inside(box, outer):
    """Is (x, y, w, h) wholly inside (x, y, w, h)?"""
    return (box[0] >= outer[0] and box[1] >= outer[1]
            and box[0] + box[2] <= outer[0] + outer[2]
            and box[1] + box[3] <= outer[1] + outer[3])


def touch(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


CARD = (392, 190)
APP = (100, 80, 1400, 900)          # a window that is not maximised
SCREEN = (1920, 1080)


def placed(target, keep=()):
    x, y = WL.tour_place(CARD, target, APP, SCREEN, keep)
    return (x, y, CARD[0], CARD[1])


@section("where the card goes: the app window first, the screen second")
def _place():
    middle = placed(None)
    check("no control: across the middle of the app, a third of the way down",
          inside(middle, APP) and abs((middle[0] + CARD[0] / 2.0) - (APP[0] + APP[2] / 2.0)) <= 1
          and middle[1] == APP[1] + (APP[3] - CARD[1]) // 3, middle)
    button = (130, 300, 90, 42)
    beside = placed(button)
    check("a small control: to its right, level with it",
          beside[0] == button[0] + button[2] + 16 and beside[1] == button[1], beside)
    wide_map = (520, 240, 960, 640)            # the map: to the window's right edge
    card = placed(wide_map)
    check("the map: the card stays inside the app window", inside(card, APP), card)
    check("and beside the map, not on it, when there is room on its left",
          not touch(card, wide_map), card)
    strip = (112, 190, 1376, 40)               # the tab strip: the window's width
    card = placed(strip)
    check("the tab strip: inside the window", inside(card, APP), card)
    check("and under it, not over it", not touch(card, strip) and card[1] >= strip[1] + strip[3], card)
    whole = (100, 80, 1400, 900)               # a control as big as the window
    card = placed(whole)
    check("a control that fills the window: still inside it", inside(card, APP), card)
    keys = [(130 + 90 * n, 820, 84, 42) for n in range(4)]
    card = placed(keys[0], keys[1:])
    check("the buttons a step names are kept clear of, all of them",
          inside(card, APP) and not any(touch(card, key) for key in keys), card)
    low = (130, 930, 84, 42)                   # at the foot of the window
    card = placed(low)
    check("a control at the foot: the card is lifted to fit, not hung off the window",
          inside(card, APP) and not touch(card, low), card)
    off = WL.tour_place(CARD, (1700, 300, 90, 42), (1500, 80, 1400, 900), SCREEN)
    check("a window hanging off the screen: the card is kept on the screen",
          0 <= off[0] <= SCREEN[0] - CARD[0] and 0 <= off[1] <= SCREEN[1] - CARD[1], off)
    check("the placing knows nothing of the toolkit", "tkinter" not in read("welcome.py"))


# ---------------------------------------------------------------------------
# On the real toolkit
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
    # Not maximised, and not in the screen's corner: where the faults showed.
    app.geometry("1400x900+120+60")
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

    def box_of(widget):
        return (widget.winfo_rootx(), widget.winfo_rooty(),
                widget.winfo_width(), widget.winfo_height())

    settle_until(lambda: app.winfo_width() >= 1390)
    pump(0.5)


@on_screen("the steps say what is there now")
def _steps():
    steps = A.TOUR_STEPS
    targets = [spec for spec, _t, _w in steps]
    check("the first four steps are where they were", targets[:4] == [
        None, "t_where", "location_box", ("pad", "signal")], targets[:4])
    for name in ("status_strip", "_keys_bar", "btn_help"):
        check("%s has a step" % name, name in targets, targets)
    settings = next(words for spec, _t, words in steps if spec == "tour_settings")
    check("Settings is described as it is: every tab named",
          all(tab in settings for tab in A.SETTINGS_TABS), settings)
    check("and no longer as it was", "Discord, Inara and backups" not in settings)
    map_words = next(words for spec, _t, words in steps if spec == "plan")
    check("the map's step says where its key is", "?" in map_words and "right-click" in map_words.lower(),
          map_words)
    check("every step's control is there to light",
          all(spec is None or A.tour_target(app, spec) is not None for spec in targets),
          [spec for spec in targets if spec is not None and A.tour_target(app, spec) is None])
    check("the keys step names the buttons it must not cover",
          set(A.TOUR_KEEP_CLEAR.get(("pad", "signal"), ())) == {("pad", "border"), ("pad", "rigs"),
                                                              ("pad", "allup")})


@on_screen("every step: the card inside the app window, the ring taking no room")
def _walk():
    below = app.plan                    # under the tab strip and the status strip
    before = (below.winfo_rooty(), app.tab_strip.winfo_height(), app.status_strip.winfo_height())
    check("the tour opens", app.start_tour(force=True))
    pump(0.4)
    tour = app.touring
    window = box_of(app)
    outside, covered, moved, unringed = [], [], [], []
    for index, (spec, title, _words) in enumerate(A.TOUR_STEPS):
        while tour.at < index:
            tour.forward()
        settle_until(lambda: tour.winfo_width() > 50)
        pump(0.25)
        window = box_of(app)
        card = box_of(tour)
        if not inside(card, window):
            outside.append((title, card, window))
        target = A.tour_target(app, spec)
        keep = [target] if target is not None else []
        keep += [A.tour_target(app, other) for other in A.TOUR_KEEP_CLEAR.get(spec, ())]
        # A control wider than the room beside it cannot be kept clear of:
        # the map fills the window's right-hand side.
        if spec in (("pad", "signal"), "tour_find", "status_strip", "_keys_bar"):
            for widget in keep:
                if widget is not None and touch(card, box_of(widget)):
                    covered.append((title, card, box_of(widget)))
        now = (below.winfo_rooty(), app.tab_strip.winfo_height(), app.status_strip.winfo_height())
        if now != before:
            moved.append((title, before, now))
        if target is not None and len([f for f in tour.ring if f.winfo_exists()]) != 4:
            unringed.append(title)
    check("no card leaves the app window - the map and the tab strip included", not outside, outside[:3])
    check("no card covers the control it is about or the buttons its words name", not covered,
          covered[:3])
    check("ringing a control moves nothing: the map is where it was, the strips their own height",
          not moved, moved[:3])
    check("every control a step is about is ringed", not unringed, unringed)
    strip_step = [i for i, (spec, _t, _w) in enumerate(A.TOUR_STEPS) if spec == "tour_find"][0]
    while tour.at > strip_step:
        tour.backward()
    pump(0.25)
    ring = [box_of(f) for f in tour.ring]
    strip = box_of(app.tab_strip)
    check("the ring is round the tab strip, not inside its layout",
          len(ring) == 4 and all(abs(b[0] - strip[0]) <= 4 or abs(b[0] - (strip[0] + strip[2])) <= 4
                                 for b in ring)
          and int(app.tab_strip.cget("highlightthickness")) == 0, (ring, strip))
    tour.finish()
    pump(0.3)
    check("finished: the ring is gone with it",
          not tour.winfo_exists() and not any(f.winfo_exists() for f in tour.ring))
    check("and nothing moved afterwards either",
          (below.winfo_rooty(), app.tab_strip.winfo_height(), app.status_strip.winfo_height()) == before)
    check("nothing was raised into the window", not trouble, trouble)


print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
