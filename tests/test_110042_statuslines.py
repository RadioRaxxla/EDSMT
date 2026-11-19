"""1.10042: SRV fuel, tonnes an hour and merits on the overlay STATUS box
(#207, #210, #232), each behind a switch in Settings.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_statuslines.py
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
TMP = tempfile.mkdtemp(prefix="edsmt-sl42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import statuslines as STL    # noqa: E402
import overlay as OV         # noqa: E402
import journal as J          # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


print("== the lines ==")
check("SRV fuel in the SRV", STL.fuel_line(True, 0.4567, False) == ("0.46 t", False), STL.fuel_line(True, 0.4567))
check("low fuel is said and flagged", STL.fuel_line(True, 0.05, True) == ("0.05 t  LOW", True))
check("no fuel line out of the SRV", STL.fuel_line(False, 0.4) is None)
check("no fuel line when the game has not said", STL.fuel_line(True, None) is None)
check("tonnes an hour", STL.tph_line(12.34) == "12.3" and STL.tph_line(0) is None and STL.tph_line(None) is None)
check("merits only when pledged", STL.merits_line("", 50) is None and STL.merits_line("Felicia Winters", 1250) == "1,250")
check("pledged with none yet reads 0", STL.merits_line("Felicia Winters", 0) == "0")
every = STL.build({}, True, 0.3, False, 9.0, "Felicia Winters", 40)
check("all three by default", set(every) == {"fuel", "tph", "merits"}, every)
off = STL.build({"overlay_status_fuel": False, "overlay_status_tph": False, "overlay_status_merits": False},
                True, 0.3, False, 9.0, "Felicia Winters", 40)
check("each switch turns its line off", off == {}, off)
check("rows come in the order fuel, t/h, merits", [r[0] for r in STL.rows(every)] == ["SRV fuel", "t/h", "Merits"])

print("== the journal reads Fuel from Status.json ==")
check("the watcher starts with no fuel figure", "fuel_main" in read("journal.py")
      and 'data.get("Fuel")' in read("journal.py"))


class _Canvas:
    def __init__(self):
        self.calls = []

    def delete(self, *_a):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kw):
            self.calls.append((name, args, kw))
        return record


class _Scaling:
    """Tk's answer to "tk scaling" on a screen at this display scaling."""
    def __init__(self, dpi):
        self.dpi = float(dpi)

    def call(self, *_a):
        return self.dpi * 96.0 / 72.0


class _Window:
    def __init__(self, w, h):
        self.w, self.h = w, h

    def winfo_width(self):
        return self.w

    def winfo_height(self):
        return self.h

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


class _App:
    def colour_for(self, name):
        return "#ff7a18"


def status(lines, size=(300, 200), dpi=1.0, whole=False):
    """What STATUS writes for these lines in a box this size. dpi is the
    display scaling the box is drawn at: the test sets it, so the answer is
    the same on a PC whose own scaling is above 100%."""
    over = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_click_through": True})
    panel = OV.Panel(over, OV.STATUS)
    panel.window = _Window(*size)
    panel.canvas = _Canvas()
    panel.canvas.tk = _Scaling(dpi)
    over.panels = {OV.STATUS: panel}
    # On Windows the boxes are drawn only while the game is in front. This
    # test is about what is drawn, so it answers that itself: without it
    # nothing at all is drawn on a real PC with no game running.
    over.follow_game = lambda: True
    over.draw([], 0.0, body="Ega 3 a", location="2", lines=lines)
    texts = [(str(kw.get("text", "")), args) for name, args, kw in panel.canvas.calls
             if name == "create_text"]
    return texts if whole else [text for text, _args in texts]


def one_line(said):
    """The single short line that carries all three, or ""."""
    for text in said:
        if "FUEL" in text and "T/H" in text and "MERITS" in text:
            return text
    return ""


print("== STATUS draws them: a row each in a tall box ==")
said = status(every, size=(300, 220))
check("SRV fuel is on the box", any("SRV FUEL" in t for t in said) and any("0.30 t" in t for t in said), said)
check("tonnes an hour is on the box", any(t == "T/H" for t in said) and any("9.0" == t for t in said), said)
check("merits is on the box", any("MERITS" in t for t in said) and any("40" == t for t in said), said)
none = status({}, size=(300, 220))
check("with no lines the box is as it was", not any("SRV FUEL" in t or "MERITS" in t for t in none), none)
only = status({"merits": "7"}, size=(300, 220))
check("a line left out is not drawn", not any("SRV FUEL" in t for t in only) and any("MERITS" in t for t in only), only)
check("the same box on a screen scaled to 200%, twice the pixels: a row each",
      any("SRV FUEL" in t for t in status(every, size=(600, 440), dpi=2.0)))

print("== and as one short line where there is no room for rows ==")
check("the words", STL.compact(every) == ("FUEL 0.30 t  9.0 T/H  40 MERITS", False), STL.compact(every))
check("LOW is said, and flagged", STL.compact({"fuel": ("0.05 t  LOW", True)}) == ("FUEL 0.05 t  LOW", True))
check("nothing to say is nothing", STL.compact({}) == ("", False) and STL.compact(None) == ("", False))
# The box as it comes on a 1080p screen: 556 x 74.
box = status(every, size=(556, 74))
check("the box as it comes (556 x 74) carries all three on one line", bool(one_line(box)), box)
check("and no rows", not any(t == "T/H" for t in box), box)
whole = status(every, size=(556, 74), whole=True)
spot = [args for text, args in whole if "FUEL" in text]
check("inside the box", bool(spot) and all(0 <= a[0] <= 556 and 0 <= a[1] <= 74 for a in spot), spot)
check("the same on a screen scaled to 150% (834 x 111) and to 200% (1112 x 148)",
      bool(one_line(status(every, size=(834, 111), dpi=1.5)))
      and bool(one_line(status(every, size=(1112, 148), dpi=2.0))))
# What failed on a real PC: a fixed 300 x 220 box drawn at 200%.
tight = status(every, size=(300, 220), dpi=2.0)
check("a box with room for some rows but not all: one short line, none left off",
      bool(one_line(tight)) and not any(t == "T/H" for t in tight), tight)
short = status(every, size=(300, 60), whole=True)
check("a short box with no bottom row: on the second line, in the key hint's place",
      bool(one_line([t for t, _a in short]))
      and all(a[1] <= 60 for t, a in short if "FUEL" in t), short)
check("with nothing to say the key hint is where it was",
      not one_line(status({}, size=(300, 60))))
check("a box too short for a second line draws none rather than draw out of the box",
      not any("MERITS" in t for t in status(every, size=(300, 34))))
check("one line alone is short enough to read", one_line(status(every, size=(240, 74))) != ""
      or any("FUEL" in t for t in status(every, size=(240, 74))))

print("== wiring ==")
src = read("edsmt.py")
for key in ("overlay_status_fuel", "overlay_status_tph", "overlay_status_merits"):
    check("%s is a default, a tip and a switch" % key, src.count(key) >= 3, src.count(key))
check("the app feeds the overlay", "lines=self.status_lines()" in src and "def status_lines" in src)
check("statuslines is in both build specs", all('"statuslines"' in read("build", s)
                                                 for s in ("EDSMT.spec", "EDSMT-onefile.spec")))
check("the guide says it", "tonnes an hour" in read("docs", "GUIDE.md").lower()
      and "SRV fuel" in read("docs", "GUIDE.md"))

print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
