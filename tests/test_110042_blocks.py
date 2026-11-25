"""1.10042 (G4, #341): distances and directions from building blocks.

When recordings of the blocks exist for a voice - every distance as one
recording of the whole phrase, and the sixteen compass points - a line
like "Nearest deposit, 2.4 kilometres north-east" is the lead, the
distance and the point joined into one recording, a breath between them
and no clipped join. When any block is missing the whole line is the
Windows voice, never half and half. 1.201: the voice picked is the only one
heard, so a recorded voice without every block says nothing; the words are
read when the Windows voice is the one picked.

    python tests/test_110042_blocks.py
"""
import os
import sys
import tempfile
import time
import wave
import array

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import voice as VO          # noqa: E402
import voiceblocks as VB    # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="edsmt-blocks-")


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


print("== every distance is one recording of the whole phrase ==")
ids = [ident for ident, _w in VB.DISTANCES]
check("288 of them, each once", len(ids) == 288 and len(set(ids)) == 288, len(ids))
check("whole metres under ten, with the singular",
      VB.WORDS["dist_m_1"] == "1 metre" and VB.WORDS["dist_m_9"] == "9 metres")
check("tens of metres under a kilometre",
      [i for i in ids if i.startswith("dist_m_")][9:] == ["dist_m_%d" % n for n in range(10, 1000, 10)])
check("tenths of a kilometre under ten, with the singular", VB.WORDS["dist_km_1"] == "1 kilometre"
      and VB.WORDS["dist_km_2p4"] == "2.4 kilometres" and VB.WORDS["dist_km_9p9"] == "9.9 kilometres")
check("whole kilometres from ten to ninety-nine", VB.WORDS["dist_km_10"] == "10 kilometres"
      and VB.WORDS["dist_km_99"] == "99 kilometres" and "dist_km_100" not in VB.WORDS)
_hits = [(i, VO.TAKE_FILE.match(i + ".wav")) for i in VB.ALL_BLOCKS]
check("no id reads as a later take of another block (<id>_2.wav is take two of <id>)",
      not [i for i, h in _hits if h and h.group("stem") in VB.ALL_BLOCKS])

print("== a distance is said as distance_words writes it ==")
bad = []
for metres in [x / 2.0 for x in range(0, 4000)] + list(range(2000, 200001, 7)):
    got, want = VB.distance_blocks(metres), VO.distance_words(metres)
    if got is None:
        if metres < 99500:
            bad.append((metres, None, want))
    elif len(got) != 1 or VB.block_words(got) != want:
        bad.append((metres, got, want))
check("every distance from nothing to 200 km: one block, the same words", not bad, bad[:4])
check("2.4 km", VB.distance_blocks(2400) == ["dist_km_2p4"], VB.distance_blocks(2400))
check("340 m, and 344 m to the nearest ten", VB.distance_blocks(340) == ["dist_m_340"] == VB.distance_blocks(344))
check("one metre and one kilometre have their own recording",
      VB.distance_blocks(1) == ["dist_m_1"] and VB.distance_blocks(1000) == ["dist_km_1"])
check("under a metre is one metre", VB.distance_blocks(0) == ["dist_m_1"])
check("ten kilometres and over is said to the whole kilometre",
      VB.distance_blocks(12345) == ["dist_km_12"] and VO.distance_words(12345) == "12 kilometres"
      and VB.distance_blocks(9960) == ["dist_km_10"], (VB.distance_blocks(12345), VO.distance_words(12345)))
check("a hundred kilometres and more has no recording", VB.distance_blocks(99499) == ["dist_km_99"]
      and VB.distance_blocks(120000) is None and VO.distance_words(120000) == "120 kilometres")
check("rubbish: none", VB.distance_blocks("x") is None and VB.distance_blocks(None) is None
      and VB.distance_blocks(float("nan")) is None)

print("== the sixteen compass points ==")
check("sixteen of them", len(VB.COMPASS) == 16 and len({c for c, _w in VB.COMPASS}) == 16)
want = {0: "north", 22.5: "north_north_east", 45: "north_east", 67.5: "east_north_east", 90: "east",
        135: "south_east", 180: "south", 225: "south_west", 270: "west", 315: "north_west",
        350: "north", 359.9: "north", 360: "north", -90: "west", 450: "east", 200: "south_south_west"}
for bearing, ident in want.items():
    check("%s -> %s" % (bearing, ident), VB.compass_blocks(bearing) == [ident], VB.compass_blocks(bearing))
check("words are hyphenated for the Windows voice",
      VB.block_words(["north_north_east"]) == "north-north-east" and VB.block_words(["south_west"]) == "south-west")
check("no bearing, no direction", VB.compass_blocks(None) is None and VB.compass_blocks("x") is None)

print("== the line ==")
got = VB.direction_blocks("nearest", 2400, 45)
check("Nearest deposit, 2.4 kilometres north-east: the lead, the distance, the point",
      got == ["nearest", "dist_km_2p4", "north_east"], got)
check("without a lead", VB.direction_blocks("", 340, 90) == ["dist_m_340", "east"])
check("a part that cannot be said makes no line", VB.direction_blocks("nearest", 120000, 90) is None
      and VB.direction_blocks("nearest", 340, None) is None)
check("what the Windows voice says instead is the same words",
      VO.direction_text("Nearest deposit.", 2400, 45) == "Nearest deposit, 2.4 kilometres north-east",
      VO.direction_text("Nearest deposit.", 2400, 45))
check("one metre is said in the singular", VO.direction_text("", 1, 90) == "1 metre east")
check("no bearing: nothing to say", VO.direction_text("Nearest deposit", 340, None) == "")

print("== the list for the recording sheet ==")
every = VB.ALL_BLOCKS
check("304 blocks: 288 distances and the 16 points",
      len(every) == 304 and len(set(every)) == 304, len(every))
check("they are the ids the line is made of", set(VB.direction_blocks("", 12500, 337.5)) <= set(every))
folders = [os.path.join(TMP, "list")]
check("a theme with nothing lacks all of them", VO.missing_blocks("on_air", folders) == sorted(every))


def put(theme, ident, root, frames=None, rate=22050, width=2, channels=1, pad=60, amp=12000, take=""):
    folder = os.path.join(root, "voice", theme)
    os.makedirs(folder, exist_ok=True)
    body = frames if frames is not None else 1000
    samples = array.array("h", [0] * pad + [amp] * body + [0] * pad)
    with wave.open(os.path.join(folder, ident + take + ".wav"), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes((samples.tobytes() if width == 2 else bytes(len(samples) * channels)) if channels == 1
                        else array.array("h", [x for x in samples for _ in range(channels)]).tobytes())


root = os.path.join(TMP, "list")
for ident in ("dist_m_340", "north"):
    put("on_air", ident, root)
left = VO.missing_blocks("on_air", [root])
check("what is recorded is not listed, the rest is", "dist_m_340" not in left and "north" not in left
      and len(left) == 302, len(left))
check("a take counts as the block recorded", (put("on_air", "dist_m_350", root, take="_2") or True)
      and "dist_m_350" not in VO.missing_blocks("on_air", [root]))
check("a tenth of a kilometre is not a take of the whole one",
      (put("on_air", "dist_km_2p4", root) or True) and "dist_km_2" in VO.missing_blocks("on_air", [root]))

print("== Celestia's distances are a supporter's pack (1.201) ==")
check("the free install has none of them: she says no distance there",
      len(VO.missing_blocks("celestia", [REPO])) == len(VO.VB.ALL_BLOCKS), len(VO.missing_blocks("celestia", [REPO])))
tenths = os.path.join(TMP, "tenths")
for ident in ("dist_km_2", "dist_km_2p4", "dist_m_1", "dist_m_10"):
    put("celestia", ident, tenths)
check("two kilometres has one recording, not its tenths as takes",
      [os.path.basename(p) for p in VO.recording_takes("dist_km_2", "celestia", [tenths])] == ["dist_km_2.wav"])
check("nor is one metre given the tens",
      [os.path.basename(p) for p in VO.recording_takes("dist_m_1", "celestia", [tenths])] == ["dist_m_1.wav"])


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


def say(theme, root, lead, metres, bearing, cache=None, text=None, comms=False, **kw):
    stand = Stand()
    sp = VO.Speaker(spawn=lambda: stand, folders=[root], cache_dir=cache or os.path.join(TMP, "cache"))
    sp.comms = comms
    ok = sp.say_direction(lead, metres, bearing, theme, text=text, **kw)
    end = time.monotonic() + (5 if ok else 0.6)
    while time.monotonic() < end and not [x for x in stand.lines if x[:2] in ("S ", "W ")]:
        time.sleep(0.01)
    time.sleep(0.05)
    sp.close()
    return ok, [x for x in stand.lines if x[:2] in ("S ", "W ")], sp


def full(theme, root, **kw):
    for ident in VB.ALL_BLOCKS + ("nearest",):
        put(theme, ident, root, **kw)


GAP = int(22050 * VB.JOIN_GAP_MS / 1000.0)
STEP = 1000 + GAP
print("== all the blocks there: one joined recording ==")
for theme in ("celestia", "ship_computer", "flight_controller", "on_air"):
    root = os.path.join(TMP, "full-" + theme)
    full(theme, root)
    ok, got, sp = say(theme, root, "nearest", 2400, 45)
    check("%s: said, as one file" % theme, ok and len(got) == 1 and got[0].startswith("W "), got)
    if got and got[0].startswith("W "):
        path = got[0][2:]
        with wave.open(path, "rb") as w:
            frames = w.getnframes()
            data = array.array("h", w.readframes(frames))
        # nearest, dist_km_2p4, north_east: three blocks of 1000 frames, their
        # own silence trimmed, a breath between one and the next
        check("%s: a breath between the parts and nothing else added" % theme,
              VB.JOIN_GAP_MS > 0 and frames == 3000 + 2 * GAP, frames)
        check("%s: the breath is silence" % theme,
              not any(data[1000:STEP]) and not any(data[STEP + 1000:2 * STEP]))
        edges = [data[i * STEP] for i in range(3)] + [data[i * STEP + 999] for i in range(3)]
        check("%s: no clipped join - every part starts and ends near silence" % theme,
              all(abs(x) < 1500 for x in edges), edges)
        check("%s: the middle is untouched" % theme, data[500] == 12000 and data[STEP + 500] == 12000)
    check("%s: it is in the history as the words" % theme,
          sp.history() and sp.history()[0][1] == VO.direction_text(VO.line_text("nearest", theme), 2400, 45),
          sp.history())

print("== joined with no breath when none is asked for ==")
root = os.path.join(TMP, "full-on_air")
tight = os.path.join(TMP, "tight.wav")
pair = [os.path.join(root, "voice", "on_air", n + ".wav") for n in ("nearest", "north")]
check("joined", VB.join_wavs(pair, tight))
with wave.open(tight, "rb") as w:
    check("two blocks of 1000 frames, no gap", w.getnframes() == 2000, w.getnframes())
check("the breath is part of the name the join is kept under",
      VB.joined_path(pair, TMP) != VB.joined_path(pair, TMP, VB.JOIN_GAP_MS))

print("== Celestia with her comm sound: still one recording ==")
root = os.path.join(TMP, "full-celestia")
ok, got, _sp = say("celestia", root, "nearest", 2400, 45, comms=True)
check("one file, played", ok and len(got) == 1 and got[0].startswith("W "), got)

print("== the same line twice joins once ==")
root = os.path.join(TMP, "full-on_air")
cache = os.path.join(TMP, "cache2")
a = say("on_air", root, "nearest", 340, 90, cache=cache)[1][0][2:]
b = say("on_air", root, "nearest", 340, 90, cache=cache)[1][0][2:]
check("the same file", a == b, (a, b))
check("kept in the cache folder", os.path.dirname(a) == cache or os.path.dirname(a).startswith(cache), a)

print("== any block missing: a recorded voice says none of it (1.201) ==")
root = os.path.join(TMP, "gap")
full("on_air", root)
os.remove(os.path.join(root, "voice", "on_air", "dist_km_2p4.wav"))
ok, got, _sp = say("on_air", root, "nearest", 2400, 45, text="Nearest deposit, 2.4 kilometres north-east")
check("nothing is said: not half, and not read by another voice", ok is False and got == [], (ok, got))
ok, got, _sp = say("windows", root, "nearest", 2400, 45, text="Nearest deposit, 2.4 kilometres north-east")
check("the Windows voice, picked, reads the whole line",
      ok and got == ["S Nearest deposit, 2.4 kilometres north-east"], got)
check("and plays no other voice's recording", not [x for x in got if x.startswith("W ")])
ok, got, _sp = say("on_air", root, "nearest", 340, 90)
check("a line that does not need the missing block is still joined", got and got[0].startswith("W "), got)
root2 = os.path.join(TMP, "nolead")
full("on_air", root2)
os.remove(os.path.join(root2, "voice", "on_air", "nearest.wav"))
ok, got, _sp = say("on_air", root2, "nearest", 340, 90)
check("the lead's recording missing is the same: nothing said", ok is False and got == [], got)
ok, got, _sp = say("on_air", os.path.join(TMP, "none"), "nearest", 340, 90)
check("no blocks at all: nothing said", ok is False and got == [], got)
ok, got, _sp = say("on_air", root, "nearest", 250000, 90)
check("a distance with no recording: nothing said", ok is False and got == [], got)
ok, got, _sp = say("windows", root, "nearest", 250000, 90)
check("the Windows voice reads it, in words",
      (got and got[0].startswith("S ") and "250 kilometres" in got[0]), got)

print("== blocks that do not match each other ==")
root = os.path.join(TMP, "mismatch")
full("on_air", root)
put("on_air", "dist_km_2p4", root, rate=44100)
ok, got, _sp = say("on_air", root, "nearest", 2400, 45)
check("a different sample rate: nothing is said, and the fault is kept", got == [] and bool(_sp.problem()), (got, _sp.problem()))
root = os.path.join(TMP, "broken")
full("on_air", root)
open(os.path.join(root, "voice", "on_air", "north_east.wav"), "wb").write(b"not a wave")
ok, got, _sp = say("on_air", root, "nearest", 2400, 45)
check("a file that is not a wave: nothing said, no crash", got == [] and bool(_sp.problem()), (got, _sp.problem()))
root = os.path.join(TMP, "silent")
full("on_air", root)
put("on_air", "dist_km_2p4", root, frames=0, pad=40)
ok, got, _sp = say("on_air", root, "nearest", 2400, 45)
check("a block that is only silence: nothing said", got == [] and bool(_sp.problem()), (got, _sp.problem()))

print("== a Speaker that cannot speak ==")
sp = VO.Speaker(spawn=None, folders=[TMP])
sp.spawn = None
check("says nothing, returns False", sp.say_direction("nearest", 340, 90, "on_air") is False)

print("== the app's spoken directions use it ==")
try:
    import tkinter
    tkinter.Tk().destroy()
    os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
    os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
    os.environ["HOME"] = TMP
    import edsmt as A
except Exception as exc:
    A = None
    print("  SKIP  needs a display (%s)" % exc)
if A is not None:
    class Fake:
        def __init__(self):
            self.said = []
            self.folders = []
            self.comms = True

        def set_rate(self, rate):
            pass

        def say_words(self, text, theme=None):
            self.said.append(("text", text, theme))
            return VO.reads_words(theme)

        def say_direction(self, lead, metres, bearing, theme, place=None, detail=None, text=None):
            self.said.append(("blocks", lead, metres, bearing, theme, text))
            return True

    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = {"voice_directions": True, "voice_theme": "on_air", "voice_comms": False}
    app.directions = None
    app.voice = Fake()
    app.game = None
    view = {"rhino": True, "moving": True,
            "deposit": {"key": "deposit:7", "name": "Platinum", "range_m": 340.0, "offset": 60.0, "bearing": 45.0}}
    words = app.say_directions(view, now=1000.0)
    check("the deposit's line goes to say_direction, with its compass bearing, in the picked voice",
          app.voice.said and app.voice.said[0][:5] == ("blocks", "nearest", 340.0, 45.0, "on_air"), app.voice.said)
    check("the words the Windows voice would say are still those of before",
          app.voice.said[0][5] == "Platinum, 340 metres, two o'clock" == words, (app.voice.said, words))
    check("comm effects off reaches the speaker", app.voice.comms is False)
    app.voice.said.clear()
    view = {"rhino": True, "moving": True,
            "pin": {"key": "pin:2", "name": "Pin 2", "range_m": 80.0, "offset": 0.0}}
    words = app.say_directions(view, now=2000.0)
    check("a pin has no compass bearing: its words are asked of the voice picked, which has none (1.201)",
          app.voice.said and app.voice.said[0][0] == "text" and app.voice.said[0][2] == "on_air" and words == "",
          (app.voice.said, words))
    app.voice.said.clear()
    app.settings["voice_theme"] = "windows"
    app.directions = None
    words = app.say_directions(view, now=3000.0)
    check("with Windows voice picked they are read, as before",
          app.voice.said and app.voice.said[0][:2] == ("text", words) and words.startswith("Pin 2, 80 metres"),
          (app.voice.said, words))

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
