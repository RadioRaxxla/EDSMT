"""1.10042: how long a hold counts as a rig placed is the commander's to set.

Two testers: the hold that places a rig in the game is not the same for
everyone - one needs up to four seconds, another three - and EDSMT counted
a rig at two seconds whatever the commander's own hold was. Settings ->
Rigs now has "Hold for", from 1 to 5 seconds, 2 as before.

    python tests/test_110042_righold.py
"""
import os
import queue
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import inputdev as IND     # noqa: E402
import inputmix as IM      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


print("== the setting, read safely ==")
check("two seconds unless told otherwise", IND.LONG_PRESS_S == 2.0 and IND.hold_seconds(None) == 2.0
      and IND.hold_seconds("") == 2.0)
check("a number, or a number as text", IND.hold_seconds(3) == 3.0 and IND.hold_seconds("3.5") == 3.5)
check("never under one second", IND.hold_seconds(0.2) == 1.0 and IND.hold_seconds(-4) == 1.0)
check("never over five", IND.hold_seconds(9) == 5.0)
check("rubbish is the default, not a crash", IND.hold_seconds("long") == 2.0 and IND.hold_seconds([]) == 2.0
      and IND.hold_seconds(float("nan")) == 2.0)
check("the limits are named", (IND.HOLD_MIN_S, IND.HOLD_MAX_S) == (1.0, 5.0))

print("== what a press of a given length is ==")
check("as before with nothing set: 2 s is a rig", IND.press_kind(2.0) == "rig" and IND.press_kind(1.9) == "between"
      and IND.press_kind(0.3) == "click")
check("set to 3 s, 2.4 s is no longer a rig", IND.press_kind(2.4, 3) == "between", IND.press_kind(2.4, 3))
check("and 3 s is", IND.press_kind(3.0, 3) == "rig")
check("set to 1 s, 1 s is", IND.press_kind(1.0, 1) == "rig" and IND.press_kind(0.9, 1) == "between")
check("a click is a click whatever the hold", IND.press_kind(0.3, 5) == "click")


def held(watcher, seconds, step=0.05):
    """Hold the button for `seconds` and say when (if ever) it counted."""
    now, fired = 100.0, None
    watcher.reset()
    watcher.step(False, True, now)
    ticks = int(round(seconds / step))
    for tick in range(1, ticks + 2):
        now += step
        if watcher.step(True, True, now):
            fired = round((tick - 1) * step, 2)
    watcher.step(False, True, now + step)
    return fired


def at(fired, seconds):
    """Counted at `seconds`, give or take one look (a look is 0.05 s)."""
    return fired is not None and seconds - 0.001 <= fired <= seconds + 0.051


print("== the fire binding, held ==")
watcher = IND.HoldWatcher()
check("with nothing set it counts at 2 s", at(held(watcher, 2.5), 2.0), held(watcher, 2.5))
watcher.hold_s = 3.0
check("set to 3 s: 2.5 s does not count", held(watcher, 2.5) is None, held(watcher, 2.5))
check("3.2 s does, at 3 s, once", at(held(watcher, 3.2), 3.0), held(watcher, 3.2))
watcher.hold_s = 4.0
check("set to 4 s: at 4 s", at(held(watcher, 4.5), 4.0), held(watcher, 4.5))
watcher.hold_s = "rubbish"
check("a bad value on the watcher is the default, not a fault", at(held(watcher, 2.5), 2.0), held(watcher, 2.5))

older = IND.LongPress("left")
older.hold_s = 3.0
now, got = 50.0, []
older.step(False, False, True, now)
for _ in range(70):
    now += 0.05
    hit = older.step(True, False, True, now)
    if hit:
        got.append(round(now - 50.05, 2))
check("the mouse watcher kept for older callers follows it too", len(got) == 1 and at(got[0], 3.0), got)

print("== the app hands the setting to the watcher ==")
check("the default is in the helper", IM.hold_for({}) == 2.0 and IM.hold_for(None) == 2.0)
check("the setting is read as seconds", IM.hold_for({"long_press_seconds": "3"}) == 3.0
      and IM.hold_for({"long_press_seconds": 4.5}) == 4.5)
check("and kept within 1 to 5", IM.hold_for({"long_press_seconds": "60"}) == 5.0)


class Keys:
    def __init__(self):
        self.events = queue.Queue()


class Game:
    in_rhino = True
    in_srv = True


class Reader:
    down = False

    def any_down(self, _inputs):
        return self.down

    def forget(self):
        pass


class Front:
    def elite_in_front(self):
        return True

    def available(self):
        return True


class App:
    def __init__(self, seconds):
        self.settings = {"long_press_rig": True, "long_press_button": "primary",
                         "long_press_seconds": seconds}
        self.game = Game()
        self.hotkeys = Keys()
        self.troubles = []

    def after(self, _ms, _fn=None, *rest):
        return "timer"

    def trouble(self, what, exc):
        self.troubles.append((what, repr(exc)))


def through_the_app(seconds, hold):
    app = App(seconds)
    st = IM.state(app)
    st.reader, st.mouse = Reader(), Front()
    clock = [500.0]
    st.clock = lambda: clock[0]
    st.binds, st.binds_at = {}, clock[0] + 10 ** 6
    IM.mouse_tick(app)
    st.reader.down = True
    for _ in range(int(round(hold * 20)) + 1):
        clock[0] += 0.05
        IM.mouse_tick(app)
    st.reader.down = False
    clock[0] += 0.05
    IM.mouse_tick(app)
    out = []
    while not app.hotkeys.events.empty():
        out.append(app.hotkeys.events.get())
    return out, app.troubles


check("set to 3 s in Settings, a 2.5 s hold places no rig", through_the_app("3", 2.5) == ([], []),
      through_the_app("3", 2.5))
check("a 3.2 s hold places one", through_the_app("3", 3.2) == (["rigs"], []), through_the_app("3", 3.2))
check("left at 2 s, a 2.2 s hold still places one", through_the_app("2", 2.2) == (["rigs"], []),
      through_the_app("2", 2.2))
check("a change in Settings is followed without a restart", "st.hold.hold_s = hold_for(" in
      open(os.path.join(REPO, "inputmix.py"), encoding="utf-8").read().split("def mouse_tick")[1].split("\ndef ")[0])

print("== Settings ==")
source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
check("a default of 2 s", '"long_press_seconds": "2"' in source)
rigs_page = source.split('self._section(body, "Long press for a rig"')[1].split("self.binds_line")[0]
check("a choice on the Rigs page, under the switch",
      'self._choice(body, "long_press_seconds", "Hold for"' in rigs_page)
check("from 1 to 5 seconds", all('"%s"' % value in rigs_page for value in ("1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5")))
check("the page no longer says two seconds as a fixed fact", "held for two seconds counts" not in rigs_page)
check("it has a tip", '"long_press_seconds":' in source.split("SETTING_TIPS = {")[1].split("\n}\n")[0])
guide = open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
check("the guide says the hold can be set", "1 to 5 seconds" in guide, "docs/GUIDE.md")

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
