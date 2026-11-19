"""1.10042 (G5): Flight controller and Radio Raxxla on-air, wired like Celestia.

Choosing either plays its recordings when they are there and speaks the
line with the Windows voice when they are not. Every line id the app speaks
has an entry for both. The list of lines still to record is a function.

    python tests/test_110042_themes.py
"""
import glob
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import voice as VO      # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="edsmt-themes-")


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


class Stand:
    def __init__(self):
        self.lines = []
        self.stdin = self
        self.stderr = None

    def write(self, data):
        self.lines.append(data.decode("utf-8").strip())

    def flush(self):
        pass

    def close(self):
        pass

    def poll(self):
        return None

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


def said(theme, line_id, folders, place=None):
    stand = Stand()
    sp = VO.Speaker(spawn=lambda: stand, folders=folders)
    sp.say_line(line_id, theme, place=place)
    end = time.monotonic() + 3
    while time.monotonic() < end and not [x for x in stand.lines if x[:2] in ("S ", "W ")]:
        time.sleep(0.01)
    sp.close()
    return [x for x in stand.lines if x[:2] in ("S ", "W ")]


print("== every line the app speaks has an entry in both themes ==")
ids = set()
for path in glob.glob(os.path.join(REPO, "*.py")):
    text = open(path, encoding="utf-8").read()
    ids |= set(re.findall(r"\bspeak(?:_sweep)?\(\s*\"([a-z_0-9]+)\"", text))
ids |= {VO.rig_line(kind, n) for kind in ("up", "down") for n in range(1, 7)}
ids |= {line for line in VO.SWEEP_LINES}
ids |= {"wing_linked", "wing_mate_joined", "wing_mate_left", "chat_ok", "chat_unknown",
        "session_start", "session_paused", "session_resumed", "session_end"}
ids.discard("")
check("a good many ids found in the app", len(ids) > 30, len(ids))
spoken_only = set(VO.SPOKEN_ONLY)
for theme in ("flight_controller", "on_air"):
    lacking = sorted(i for i in ids if i not in spoken_only and not VO.line_text(i, theme))
    check("%s: every id the app speaks has its words" % theme, not lacking, lacking)
lacking = sorted(i for i in ids if i not in spoken_only and not VO.line_text(i, "celestia"))
check("celestia: the same", not lacking, lacking)
check("the functions that pick a line only give ids the pack has",
      all(VO.session_line(a, b) in (None, "") or VO.line_text(VO.session_line(a, b), "on_air")
          for a in ("", "running", "paused", "ended") for b in ("", "running", "paused", "ended")))

print("== a recording when there is one ==")
for theme in ("flight_controller", "on_air"):
    folder = os.path.join(TMP, "a-" + theme, "voice", theme)
    os.makedirs(folder)
    open(os.path.join(folder, "signal_logged.wav"), "wb").write(b"RIFF")
    got = said(theme, "signal_logged", [os.path.join(TMP, "a-" + theme)])
    check("%s: the file is played, nothing is spoken" % theme,
          len(got) == 1 and got[0].startswith("W ") and got[0].endswith("signal_logged.wav"), got)
    got = said(theme, "signal_logged", [os.path.join(TMP, "a-" + theme)], place="srv")
    check("%s: in the Rhino it still plays the clean file, with no comm sound" % theme,
          len(got) == 1 and got[0].startswith("W ") and "srv" not in got[0], got)

print("== the Windows voice when there is not ==")
for theme in ("flight_controller", "on_air"):
    got = said(theme, "signal_logged", [os.path.join(TMP, "none")])
    words = VO.line_text("signal_logged", theme)
    check("%s: the words, spoken" % theme, got == ["S " + words] and words, got)
check("the two themes have words of their own",
      VO.line_text("signal_logged", "flight_controller") != VO.line_text("signal_logged", "on_air"))

print("== recordings in a folder of the other theme are not used ==")
other = os.path.join(TMP, "b", "voice", "on_air")
os.makedirs(other)
open(os.path.join(other, "border_set.wav"), "wb").write(b"RIFF")
got = said("flight_controller", "border_set", [os.path.join(TMP, "b")])
check("Flight controller does not play On-air's file", got and got[0].startswith("S "), got)

print("== the list of lines still to record ==")
folder = os.path.join(TMP, "c", "voice", "on_air")
os.makedirs(folder)
for i in ("signal_logged", "border_set"):
    open(os.path.join(folder, i + ".wav"), "wb").write(b"RIFF")
left = VO.unrecorded("on_air", [os.path.join(TMP, "c")])
check("what has a file is not listed", "signal_logged" not in left and "border_set" not in left)
check("what has none is", "mined_out" in left and "rig_down_1" in left)
check("only lines of the pack are listed", set(left) <= set(VO.LINES))
check("a theme with no folder lists them all", VO.unrecorded("flight_controller", [os.path.join(TMP, "nope")])
      == sorted(VO.LINES))
check("takes count as the line recorded", "plan_ready" not in
      (lambda: (open(os.path.join(folder, "plan_ready_2.wav"), "wb").write(b"R"),
                VO.unrecorded("on_air", [os.path.join(TMP, "c")]))[1])())

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
