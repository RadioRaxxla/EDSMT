"""1.201: a voice says only what it has recorded.

The voice picked in Settings is the only voice heard. A line it has no
recording of is not said - no other voice reads it in its place, and nor is a
distance, a direction or the "Still there?" question. The Windows voice is a
voice like the others: it reads words, and only when it is the one picked.

    python tests/test_1201_voice_own.py
"""
import array
import io
import math
import os
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import voice as VO          # noqa: E402
import voiceblocks as VB    # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="edsmt-voice-own-")
RECORDED = ("celestia", "ship_computer", "flight_controller", "on_air")


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


class Stand:
    """A speech process that only notes what it is handed."""

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


def tone(seconds=0.08, rate=22050):
    """A short recording that is not silence."""
    frames = array.array("h", (int(8000 * math.sin(i * 0.2)) for i in range(int(seconds * rate))))
    if sys.byteorder == "big":
        frames.byteswap()
    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames.tobytes())
    return out.getvalue()


def put(root, theme, name, data=None):
    path = os.path.join(root, "voice", theme, *name.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(tone() if data is None else data)
    return path


def heard(act, folders, wait=0.6):
    """(what act() gave back, the lines the speech process was handed that
    make a sound, the speaker). Waits for a line, or to be sure none comes."""
    stand = Stand()
    sp = VO.Speaker(spawn=lambda: stand, folders=folders, cache_dir=os.path.join(TMP, "cache"))
    sp.comms = False
    got = act(sp)
    end = time.monotonic() + (3.0 if got else wait)
    while time.monotonic() < end and not [x for x in stand.lines if x[:2] in ("S ", "W ", "B ")]:
        time.sleep(0.01)
    time.sleep(0.05)
    sp.close()
    return got, [x for x in stand.lines if x[:2] in ("S ", "W ", "B ")], sp


EMPTY = os.path.join(TMP, "empty")
os.makedirs(EMPTY)

print("== a recorded voice with no recording of the line says nothing ==")
for theme in RECORDED:
    got, lines, _sp = heard(lambda sp, t=theme: sp.say_line("signal_logged", t), [EMPTY])
    check("%s: nothing is said, and it says so" % theme, got is False and lines == [], (got, lines))
check("the voices that read words: the Windows voice and no other",
      [key for key, _name in VO.THEMES if VO.reads_words(key)] == ["windows"])

print("== its own recording is played ==")
for theme in RECORDED:
    root = os.path.join(TMP, "own-" + theme)
    path = put(root, theme, "signal_logged.wav")
    got, lines, _sp = heard(lambda sp, t=theme: sp.say_line("signal_logged", t), [root])
    check("%s: its recording, and only that" % theme, got is True and lines == ["W " + path], lines)

print("== another voice's recording is never borrowed ==")
root = os.path.join(TMP, "borrow")
put(root, "ship_computer", "border_set.wav")
put(root, "celestia", "border_set.wav")
for theme in ("flight_controller", "on_air"):
    got, lines, _sp = heard(lambda sp, t=theme: sp.say_line("border_set", t), [root])
    check("%s does not play the Ship computer's or Celestia's" % theme, got is False and lines == [], lines)

print("== Celestia's own lines: said when she has them, silent when she has not ==")
root = os.path.join(TMP, "extras")
put(root, "celestia", "online.wav")
for line_id in ("react_jump", "hint_deploy_srv", "lore_raxxla"):
    got, lines, _sp = heard(lambda sp, i=line_id: sp.say_line(i, "celestia", detail="chatty"), [root])
    check("%s with no recording: not said, not read out" % line_id, got is False and lines == [], lines)
path = put(root, "celestia", "react_jump.wav")
got, lines, _sp = heard(lambda sp: sp.say_line("react_jump", "celestia", detail="normal"), [root])
check("with her recording it is played", got is True and lines == ["W " + path], lines)

print("== a later take or a Short one that is not here: her usual recording, still her ==")
root = os.path.join(TMP, "takes")
usual = put(root, "celestia", "deposit_marked.wav")
for _turn in range(6):
    got, lines, _sp = heard(lambda sp: sp.say_line("deposit_marked", "celestia", detail="chatty"), [root])
    if not (got is True and lines == ["W " + usual]):
        break
check("Chatty with only the first take: the first take, never words", got is True and lines == ["W " + usual], lines)
got, lines, _sp = heard(lambda sp: sp.say_line("deposit_marked", "celestia", detail="short"), [root])
check("Short with no Short recording: the same", got is True and lines == ["W " + usual], lines)

print("== the question with no recording in any voice ==")
check("it is a line of the Windows voice only", "still_there" in VO.SPOKEN_ONLY)
check("and asks with the names the buttons have now",
      "deposit depleted" in VO.SPOKEN_ONLY["still_there"].lower()
      and "mined out" not in VO.SPOKEN_ONLY["still_there"].lower(), VO.SPOKEN_ONLY["still_there"])
for theme in RECORDED:
    got, lines, _sp = heard(lambda sp, t=theme: sp.say_line("still_there", t), [EMPTY])
    check("%s does not have it read for it" % theme, got is False and lines == [], lines)
got, lines, _sp = heard(lambda sp: sp.say_line("still_there", "windows"), [EMPTY])
check("the Windows voice asks it", got is True and lines == ["S " + VO.SPOKEN_ONLY["still_there"]], lines)

print("== the Windows voice, picked, reads every Basic line ==")
got, lines, _sp = heard(lambda sp: sp.say_line("signal_logged", "windows"), [EMPTY])
check("the line's plain words", got is True and lines == ["S " + VO.line_text("signal_logged", "windows")], lines)
root = os.path.join(TMP, "win")
put(root, "celestia", "signal_logged.wav")
got, lines, _sp = heard(lambda sp: sp.say_line("signal_logged", "windows"), [root])
check("and never plays another voice's recording", lines == ["S " + VO.line_text("signal_logged", "windows")], lines)

print("== words read out: the Windows voice only ==")
for theme in RECORDED:
    got, lines, _sp = heard(lambda sp, t=theme: sp.say_words("Pin 3, 340 metres, two o'clock", t), [EMPTY])
    check("%s: not read for it" % theme, got is False and lines == [], lines)
got, lines, _sp = heard(lambda sp: sp.say_words("Pin 3, 340 metres, two o'clock", "windows"), [EMPTY])
check("the Windows voice reads them", got is True and lines == ["S Pin 3, 340 metres, two o'clock"], lines)

print("== a distance and a direction ==")
WORDS = "Platinum, 2.4 kilometres, two o'clock"
blocks = VB.direction_blocks("nearest", 2400.0, 45.0)
check("the blocks for the test are known", bool(blocks) and blocks[0] == "nearest", blocks)
root = os.path.join(TMP, "dir-none")
put(root, "celestia", "nearest.wav")
got, lines, _sp = heard(lambda sp: sp.say_direction("nearest", 2400.0, 45.0, "celestia", text=WORDS), [root])
check("a recorded voice without every block: nothing said, not half, not read out",
      got is False and lines == [], (got, lines))
root = os.path.join(TMP, "dir-all")
for ident in blocks:
    put(root, "celestia", ident + ".wav")
got, lines, _sp = heard(lambda sp: sp.say_direction("nearest", 2400.0, 45.0, "celestia", text=WORDS), [root])
check("with every block: one recording, in her voice",
      got is True and len(lines) == 1 and lines[0].startswith("W "), lines)
got, lines, _sp = heard(lambda sp: sp.say_direction("nearest", 2400.0, 45.0, "windows", text=WORDS), [root])
check("the Windows voice reads the words it was given", got is True and lines == ["S " + WORDS], lines)
got, lines, _sp = heard(lambda sp: sp.say_direction("nearest", 250000.0, 45.0, "celestia", text=WORDS), [root])
check("a distance she has no recording of: nothing said", got is False and lines == [], lines)
root = os.path.join(TMP, "dir-bad")
for ident in blocks:
    put(root, "celestia", ident + ".wav", data=b"not a wave at all")
began = time.time()
got, lines, sp = heard(lambda sp: sp.say_direction("nearest", 2400.0, 45.0, "celestia", text=WORDS), [root], wait=1.5)
check("blocks that will not join: nothing is read in their place", lines == [], lines)
check("and what went wrong is kept for Settings to show", bool(sp.problem(since=began)), sp.problem())

print("== the app: spoken directions follow the voice picked ==")
# The app is loaded with a data folder of this test's own, never the
# commander's.
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
try:
    import edsmt as A
except Exception as exc:      # no display here
    A = None
    print("  SKIP  the app could not be loaded here: %s" % exc)

if A is not None:
    class FakeSpeaker:
        def __init__(self):
            self.words, self.directions, self.folders, self.vault = [], [], [], None
            self.comms = True

        def set_rate(self, rate):
            pass

        def set_device(self, device):
            pass

        def say_words(self, text, theme=None):
            self.words.append((text, theme))
            return VO.reads_words(theme)

        def say_direction(self, lead, metres, bearing, theme=None, place=None, detail=None, text=None):
            self.directions.append((lead, theme, text))
            return VO.reads_words(theme)

    def app_with(**settings):
        app = A.EDSMT.__new__(A.EDSMT)
        app.settings = dict(A.DEFAULT_SETTINGS)
        app.settings.update(voice_mode=True, voice_directions=True, **settings)
        app.voice = FakeSpeaker()
        app.voice_packs = lambda speaker: False
        app.point_audio = lambda speaker=None: ""
        return app

    PIN = {"rhino": True, "moving": True,
           "pin": {"key": "pin:3", "name": "Pin 3", "range_m": 340.0, "offset": 60.0, "reach": 10.0}}
    DEPOSIT = {"rhino": True, "moving": True,
               "deposit": {"key": "deposit:9", "name": "Platinum", "range_m": 2400.0,
                           "bearing": 45.0, "offset": 60.0}}

    app = app_with(voice_theme="windows")
    said = app.say_directions(PIN, now=1000.0)
    check("Windows voice picked: the pin's distance and clock face are read",
          said == "Pin 3, 340 metres, two o'clock" and app.voice.words == [(said, "windows")],
          (said, app.voice.words))

    for theme in RECORDED:
        app = app_with(voice_theme=theme)
        said = app.say_directions(PIN, now=1000.0)
        check("%s picked: the pin is asked of that voice, and nothing is said for it" % theme,
              said == "" and app.voice.words == [("Pin 3, 340 metres, two o'clock", theme)],
              (said, app.voice.words))
        again = app.say_directions(PIN, now=1000.5)
        check("%s: and it is not asked again every tick" % theme, again == "" and len(app.voice.words) == 1,
              app.voice.words)

    app = app_with(voice_theme="celestia")
    said = app.say_directions(DEPOSIT, now=1000.0)
    check("the target deposit goes to the voice picked, to say from its own recordings",
          app.voice.directions and app.voice.directions[0][:2] == ("nearest", "celestia") and not app.voice.words,
          (app.voice.directions, app.voice.words))

    source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
    check("nothing in the app hands the speaker bare words any more", ".say_text(" not in source)

print("== what Settings and the guide say ==")
source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
guide = open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
notes = open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8").read().split("\n## 1.2\n")[0]
flat = " ".join(guide.split())
check("Settings no longer says Windows speaks a line with no recording",
      "A line without a recording is spoken by Windows" not in source)
check("it says a line the voice has no recording of is not said",
      "no recording of is not said" in " ".join(source.split()))
check("the guide says a voice is never filled in by another", "never filled in by another" in flat)
for old in ("a distance is read by Windows", "the whole line is spoken by Windows",
            "The other two are read by Windows' own speech", "are always read live"):
    check("the guide no longer says %r" % old, old not in flat)
check("the patch notes say it, under 1.201", "only what it has recorded" in " ".join(notes.split()))
check("and no longer that a distance is read by Windows", "a distance is read by Windows" not in " ".join(notes.split()))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
