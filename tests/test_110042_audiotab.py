"""1.10042 (G1, #361): an Audio tab in Settings.

Every voice and sound setting that was scattered - Voice Mode, the voice,
the rate, what is spoken, the spoken directions, the sonar, comm effects,
the rig warning sound, Test voice and the history of what was said - is on
one tab, each with its note. Other tabs keep at most a pointer.

    python tests/test_110042_audiotab.py
"""
import faulthandler
import json
import os
import sys
import tempfile
import time

faulthandler.dump_traceback_later(240, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-audiotab-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  needs a display (%s)" % _exc)
    sys.exit(0)

import overlay as OV      # noqa: E402
OV.foreground_is_game = lambda: None
import voice as VO        # noqa: E402
import edsmt as A         # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as fh:
    json.dump({"asked_to_share": True, "tour_done": True, "voice_asked": True,
               "welcome_seen_version": A.APP_VERSION, "journal_dir": JOURNALS}, fh)

app = A.EDSMT()
app.geometry("1400x900+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(times=3):
    for _ in range(times):
        try:
            app.update_idletasks()
            app.update()
        except Exception:
            pass


def settle_until(cond, seconds=8.0):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:
            pass
        pump(1)
        time.sleep(0.02)
    return bool(cond())


def switch_for(win, var):
    """The switch widget that holds a toggle's variable."""
    found = []

    def walk(w):
        for child in w.winfo_children():
            if getattr(child, "_variable", None) is var:
                found.append(child)
            walk(child)
    walk(win)
    return found[0] if found else None


def inside(widget, page):
    while widget is not None:
        if widget is page:
            return True
        widget = getattr(widget, "master", None)
    return False


def widgets_of(win, key):
    out = []
    if key in win.toggles:
        out.append(switch_for(win, win.toggles[key]))
    if key in win.fields:
        out.append(win.fields[key])
    if key in win.choices:
        out.append(win.choices[key][0])
    return out


def texts_in(page):
    found = []

    def walk(w):
        for child in w.winfo_children():
            try:
                found.append(str(child.cget("text")))
            except Exception:
                pass
            walk(child)
    walk(page)
    return found


print("== the tab ==")
check("an Audio tab", "Audio" in A.SETTINGS_TABS, A.SETTINGS_TABS)
check("Basics first, Theme second, still", A.SETTINGS_TABS[:2] == ("Basics", "Theme"), A.SETTINGS_TABS)
win = A.SettingsWindow(app)
pump(5)
check("the window builds an Audio page", "Audio" in win.pages)
audio = win.pages.get("Audio")

KEYS = ["voice_mode", "voice_theme", "voice_rate", "voice_detail", "voice_pack_hints",
        "voice_directions", "voice_directions_s", "sonar", "rig_warn_sound", "rig_sound_profane",
        "voice_comms"]
print("== every voice and sound setting is on it, with its note ==")
for key in KEYS:
    found = widgets_of(win, key)
    check("%s: one control, on the Audio tab" % key,
          len(found) == 1 and inside(found[0], audio), (key, len(found)))
    check("%s: its note is there" % key, bool(A.SETTING_TIPS.get(key)), key)

print("== and on no other tab ==")
for key in KEYS:
    found = widgets_of(win, key)
    others = [name for name, page in win.pages.items()
              if name != "Audio" and found and inside(found[0], page)]
    check("%s: not on %s" % (key, others or "another tab"), not others, others)

print("== the buttons ==")
words = texts_in(audio)
check("Test voice is on it", "Test voice" in words, words[:30])
check("What did it say? is on it", "What did it say?" in words, words[:30])
check("neither is left on Basics", "Test voice" not in texts_in(win.pages["Basics"])
      and "What did it say?" not in texts_in(win.pages["Basics"]))

print("== other tabs keep at most a pointer ==")
check("Basics points to the Audio tab", any("Audio" in t for t in texts_in(win.pages["Basics"])))
check("Rigs points to the Audio tab for its sound", any("Audio" in t for t in texts_in(win.pages["Rigs"])))


print("== the history of what was said, on the tab ==")
check("a line says what was said last", hasattr(win, "last_said"))
app.voice._said.append((time.time(), "Signal logged."))
win.load()
pump(3)
check("it shows the newest line", "Signal logged." in str(win.last_said.cget("text")), win.last_said.cget("text"))

print("== how much is recorded ==")
check("a line says so", hasattr(win, "recordings_note") and "of %d lines" % len(VO.LINES) in str(win.recordings_note.cget("text")),
      getattr(win, "recordings_note", None) and win.recordings_note.cget("text"))

print("== comm effects are a setting that does something ==")
check("the default is on", A.DEFAULT_SETTINGS.get("voice_comms") is True)
check("a Speaker with comms off plays the plain recording",
      VO.needs_comms(os.path.join("x", "voice", "celestia", "a.wav"), "celestia") is True
      and VO.needs_comms(os.path.join("x", "voice", "celestia", "a.wav"), "celestia", comms=False) is False)

print("== load and save keep them ==")
win.toggles["sonar"].set(True)
win.toggles["voice_comms"].set(False)
win.save() if hasattr(win, "save") else None
settle_until(lambda: json.load(open(A.SETTINGS_FILE)).get("sonar") is True)
data = json.load(open(A.SETTINGS_FILE))
check("sonar saved", data.get("sonar") is True, data)
check("comm effects off saved", data.get("voice_comms") is False, data)

print("== the guide ==")
guide = open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
check("the guide names the Audio tab", "Settings → Audio" in guide)

try:
    app.destroy()
except Exception:
    pass
print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
