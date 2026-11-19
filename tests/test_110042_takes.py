"""1.10042 (G3): more than one take of a line.

Files voice/<theme>/<id>.wav, <id>_2.wav, <id>_3.wav ... are all takes of
<id>. The one played is never the take used last time for that line, and
the last few are remembered. A line with one take is unchanged.

    python tests/test_110042_takes.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import voice as VO      # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="edsmt-takes-")


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def make(theme, *names, sub=""):
    folder = os.path.join(TMP, "voice", theme, sub) if sub else os.path.join(TMP, "voice", theme)
    os.makedirs(folder, exist_ok=True)
    for name in names:
        with open(os.path.join(folder, name), "wb") as handle:
            handle.write(b"RIFF")


class Stand:
    """A stand-in speech process that keeps what was written to it."""
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


def sent(speaker, count=1, seconds=3.0):
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        got = [x for x in speaker._proc_stand.lines if x[:2] == "W "]
        if len(got) >= count:
            return got
        time.sleep(0.01)
    return [x for x in speaker._proc_stand.lines if x[:2] == "W "]


def say_n(sp, line_id, theme, count):
    """Say a line `count` times, each once the one before has been written."""
    for n in range(count):
        sp.say_line(line_id, theme)
        sent(sp, n + 1)


def speaker_for():
    stand = Stand()
    sp = VO.Speaker(spawn=lambda: stand, folders=[TMP])
    sp._proc_stand = stand
    return sp


print("== finding the takes ==")
for theme in ("celestia", "ship_computer", "flight_controller", "on_air"):
    make(theme, "signal_logged.wav", "signal_logged_2.wav", "signal_logged_3.wav", "border_set.wav")
    got = VO.recording_takes("signal_logged", theme, [TMP])
    names = [os.path.basename(p) for p in got]
    check("%s: three takes found, in order" % theme,
          names == ["signal_logged.wav", "signal_logged_2.wav", "signal_logged_3.wav"], names)
    one = VO.recording_takes("border_set", theme, [TMP])
    check("%s: a line with one take has one" % theme,
          [os.path.basename(p) for p in one] == ["border_set.wav"], one)
    check("%s: no recording, no takes" % theme, VO.recording_takes("online", theme, [TMP]) == [])
make("celestia", "rigs_all_up.wav", "rigs_all_up_3.wav")
check("a gap in the numbers does not lose a take",
      [os.path.basename(p) for p in VO.recording_takes("rigs_all_up", "celestia", [TMP])]
      == ["rigs_all_up.wav", "rigs_all_up_3.wav"])
make("celestia", "mined_out_2.wav")
check("takes without the plain file still count",
      [os.path.basename(p) for p in VO.recording_takes("mined_out", "celestia", [TMP])] == ["mined_out_2.wav"])
make("celestia", "rig_down_1.wav", "rig_down_1_2.wav", "rig_down_10.wav")
check("rig_down_1 does not take rig_down_10",
      [os.path.basename(p) for p in VO.recording_takes("rig_down_1", "celestia", [TMP])]
      == ["rig_down_1.wav", "rig_down_1_2.wav"])

print("== the pick ==")
sp = speaker_for()
say_n(sp, "signal_logged", "ship_computer", 40)
got = sent(sp, 40)
check("forty lines said", len(got) == 40, len(got))
back = [g for a, g in zip(got, got[1:]) if a == g]
check("never the take used last time", not back, back[:2])
check("all three takes are used", len(set(got)) == 3, set(got))
recent_ok = all(len({got[i], got[i + 1], got[i + 2]}) == 3 for i in range(len(got) - 2))
check("with three takes the last two are not repeated either", recent_ok)

make("flight_controller", "plan_ready_2.wav", "plan_ready.wav")
sp = speaker_for()
say_n(sp, "plan_ready", "flight_controller", 20)
got = sent(sp, 20)
check("two takes alternate", all(a != b for a, b in zip(got, got[1:])) and len(set(got)) == 2, got[:4])

sp = speaker_for()
say_n(sp, "border_set", "on_air", 5)
got = sent(sp, 5)
check("one take: same file every time", len(got) == 5 and len(set(got)) == 1)

print("== the Windows voice when there is no recording ==")
sp = speaker_for()
sp.say_line("online", "on_air")
import time
time.sleep(0.2)
check("no file, the words are spoken", any(x.startswith("S ") for x in sp._proc_stand.lines),
      sp._proc_stand.lines)

print("== takes in the history are not confused with Chatty text takes ==")
sp = speaker_for()
check("pick_take is still 1 outside Chatty", sp.pick_take("signal_logged", "celestia", "normal") == 1)

print("== Celestia's recorded takes say a line another way ==")
check("a take's words are its own",
      VO.take_words(os.path.join("anywhere", "signal_logged_2.wav"), "celestia")
      == "Signal's ours, Commander. Centre marked.", VO.take_words("signal_logged_2.wav", "celestia"))
_third = VO.take_words("signal_logged_3.wav", "celestia")
check("with no acting directions in them", "[" not in _third and _third.startswith("Found you."), _third)
check("the first recording has none of its own", VO.take_words("signal_logged.wav", "celestia") == "")
check("nor has a take in another voice", VO.take_words("signal_logged_2.wav", "ship_computer") == "")
check("rig two's own recording is not a take of anything",
      VO.take_words("rig_down_2.wav", "celestia") == "" and VO.take_words("rig_down_2_2.wav", "celestia") == "Two's down.")
make("celestia", "arrived.wav", "arrived_2.wav")
sp = speaker_for()
say_n(sp, "arrived", "celestia", 2)
_heard = sorted(words for _when, words in sp.history())
check("What did it say? holds the words of the take that was played",
      _heard == sorted([VO.line_text("arrived", "celestia"), "That's the spot."]), _heard)

_pack = os.path.join(REPO, "voice", "celestia")
_extra = sorted(n[:-4] for n in os.listdir(_pack) if n.endswith(".wav") and n[:-4] not in VO.TAKES
                and n[:-4] not in VO.VB.ALL_BLOCKS)
check("seventy later takes ship with her pack", len(_extra) == 70, len(_extra))
check("every one has its words, and every listed take its recording",
      _extra == sorted(VO.TAKE_WORDS["celestia"]), sorted(set(_extra) ^ set(VO.TAKE_WORDS["celestia"]))[:6])
_hits = [VO.TAKE_FILE.match(n + ".wav") for n in _extra]
check("each is a take of a line of the pack",
      all(h and h.group("stem") in VO.TAKES and int(h.group("n")) >= 2 for h in _hits))
check("and the app finds it with that line",
      all(os.path.join(_pack, n + ".wav") in VO.recording_takes(h.group("stem"), "celestia", [REPO])
          for n, h in zip(_extra, _hits) if h))
_bad = []
for _name in _extra:
    _raw = open(os.path.join(_pack, _name + ".wav"), "rb").read(44)
    if not (_raw[:4] == b"RIFF" and _raw[8:12] == b"WAVE" and _raw[20:22] == b"\x01\x00"
            and int.from_bytes(_raw[22:24], "little") == 1 and int.from_bytes(_raw[24:28], "little") == 22050
            and int.from_bytes(_raw[34:36], "little") == 16):
        _bad.append(_name)
check("each is plain PCM, mono, 22 kHz, 16-bit", not _bad, _bad[:5])
check("no line is left saying the same thing as its first take",
      all(VO.TAKE_WORDS["celestia"][n] != VO.line_text(h.group("stem"), "celestia")
          for n, h in zip(_extra, _hits) if h))

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
