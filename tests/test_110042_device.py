"""1.10042 (G2): a choice of output device for EDSMT's voice and sounds.

The default is the system's default device. A chosen device that is gone
falls back to the default. The list of devices and the way of pointing the
speech process at one sit behind an object a test can replace. Nothing here
needs Windows: the stand-ins do what Windows does.

    python tests/test_110042_device.py
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
TMP = tempfile.mkdtemp(prefix="edsmt-device-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import audiodev as AD       # noqa: E402
import voice as VO          # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def wait_for(test, seconds=6.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.01)
    return bool(test())


HEADSET = "{0.0.0.00000000}.{aaaa-1111}"
SPEAKERS = "{0.0.0.00000000}.{bbbb-2222}"
OUT = ("%s\tHeadset (USB Audio)\r\n%s\tSpeakers (Realtek)\r\n\r\nnot a device line\r\n" % (HEADSET, SPEAKERS)).encode("utf-8")

print("== reading the list Windows gives ==")
got = AD.parse_devices(OUT)
check("two devices, id and name", got == [(HEADSET, "Headset (USB Audio)"), (SPEAKERS, "Speakers (Realtek)")], got)
check("a name with a tab in it keeps the rest", AD.parse_devices(b"id1\tName\twith tab\n") == [("id1", "Name\twith tab")])
check("nothing, or rubbish, is an empty list", AD.parse_devices(b"") == [] and AD.parse_devices(None) == []
      and AD.parse_devices(b"\xff\xfe") == [])
check("the same device twice is listed once",
      len(AD.parse_devices(b"a\tOne\na\tOne\nb\tTwo\n")) == 2)

print("== the choices a box offers ==")
choices = AD.device_choices(got)
check("the system default first, whatever the list", choices[0] == ("System default", ""), choices)
check("then each device by name", [n for n, _v in choices[1:]] == ["Headset (USB Audio)", "Speakers (Realtek)"])
check("two with the same name are told apart",
      len({n for n, _v in AD.device_choices([("a", "Speakers"), ("b", "Speakers")])}) == 3)
check("a chosen device that is not in the list is still offered, as not connected, so Save keeps it",
      AD.device_choices(got, keep="gone-id")[-1] == ("Chosen device (not connected)", "gone-id"))
check("but not twice, and not when it is there", AD.device_choices(got, keep=HEADSET) == choices)

print("== choosing, with a fall back ==")
check("nothing chosen: the default", AD.choose("", got) == ("", ""))
check("a device that is there", AD.choose(HEADSET, got) == (HEADSET, ""))
dev, note = AD.choose("gone-id", got)
check("a device that is gone: the default, and it says so", dev == "" and "default" in note.lower(), (dev, note))
check("a list not read yet (None) does not throw the choice away", AD.choose(HEADSET, None) == (HEADSET, ""))
check("an empty list is a list: nothing is there", AD.choose(HEADSET, [])[0] == "")
check("rubbish for the saved choice is the default", AD.choose(None, got) == ("", "") and AD.choose(5, got) == ("", ""))

print("== the list, behind an object a test can replace ==")


class FakeBackend:
    available = True

    def __init__(self, items):
        self.items, self.calls = items, 0

    def devices(self):
        self.calls += 1
        return list(self.items)


back = FakeBackend(got)
listing = AD.DeviceList(back)
check("not read until asked", listing.items() is None and not listing.ready and back.calls == 0)
listing.reload()
check("read off the caller's thread, and then there", wait_for(lambda: listing.ready), listing.ready)
check("the list is what the backend gave", listing.items() == got)
back.items = [(SPEAKERS, "Speakers (Realtek)")]
listing.reload()
check("a refresh shows the change", wait_for(lambda: listing.items() == [(SPEAKERS, "Speakers (Realtek)")]), listing.items())


class Broken:
    available = True

    def devices(self):
        raise OSError("no PowerShell")


bad = AD.DeviceList(Broken())
bad.reload()
check("a backend that fails gives an empty list, not a crash", wait_for(lambda: bad.ready) and bad.items() == [])
check("and says why", "no PowerShell" in bad.problem, bad.problem)
check("no backend at all (not Windows): nothing to choose from",
      AD.DeviceList(AD.NoDevices()).available is False and AD.NoDevices().devices() == [])
check("the real backend is only on Windows", (AD.windows_backend(VO.powershell_command).available) == (os.name == "nt"))
check("with a runner that is handed a script and returns bytes, it reads the list",
      AD.WindowsDevices(lambda script: OUT).devices() == got)
check("a runner that fails is an empty list with the reason kept",
      (lambda b: (b.devices(), b.problem))(AD.WindowsDevices(lambda script: (_ for _ in ()).throw(OSError("x")))) [0] == [])

print("== what is handed to PowerShell ==")
ls = AD.LIST_SCRIPT
check("the list script asks for audio render (output) devices only",
      "GetAudioRenderSelector" in ls and "FindAllAsync" in ls and "Windows.Devices.Enumeration" in ls)
check("and writes each as id, a tab, the name, in UTF-8", "OutputEncoding" in ls and '`t' in ls)
ss = AD.DEVICE_SPEECH_SCRIPT
check("the speech script keeps every command of the plain one, R S and W",
      all(token in ss for token in ("$what -eq 'R'", "$what -eq 'S'", "$what -eq 'W'")))
check("and has D, a device", "$what -eq 'D'" in ss)
check("a device is pointed at through the player's AudioDevice", "AudioDevice" in ss and "MediaPlayer" in ss)
check("speech to a device goes by a wave file and the same player", "SetOutputToWaveFile" in ss
      and "SetOutputToDefaultAudioDevice" in ss)
check("with no device, or no Windows Runtime, the old way: speech and the sound player",
      "$voice.Speak($text)" in ss.replace("$rest", "$text") or "$voice.Speak(" in ss)
check("a failure to point is reported and the default is used", "'E D '" in ss and "$device = $null" in ss)
check("failures are reported as in the plain script", "[Console]::Error.WriteLine('E ' + $what" in ss)
check("it is handed over encoded like the plain one", VO.powershell_command(ss)[-2] == "-EncodedCommand")
check("the plain script is untouched by all this", "AudioDevice" not in VO.SPEECH_SCRIPT)

print("== the speaker, pointed at a device ==")


class Stand:
    def __init__(self):
        self.lines = []
        self.stdin = self
        self.stderr = None
        self.dead = False

    def write(self, data):
        self.lines.append(data.decode("utf-8").strip())

    def flush(self):
        pass

    def close(self):
        pass

    def poll(self):
        return 1 if self.dead else None

    def kill(self):
        self.dead = True

    def wait(self, timeout=None):
        return 0


made = []


def plain():
    made.append("plain")
    stand = Stand()
    stands.append(stand)
    return stand


def pointed():
    made.append("pointed")
    stand = Stand()
    stands.append(stand)
    return stand


stands = []
sp = VO.Speaker(spawn=plain, folders=[TMP])
sp.spawn_device = pointed
sp.say_text("Hello")
wait_for(lambda: stands and any(x.startswith("S ") for x in stands[0].lines))
check("no device: the plain process, no D line", made == ["plain"] and not any(x.startswith("D ") for x in stands[0].lines), (made, stands[0].lines))
sp.set_device(HEADSET)
sp.say_text("Two")
wait_for(lambda: len(stands) == 2 and any(x.startswith("S ") for x in stands[1].lines))
check("a device chosen: the process is started again, the pointed kind", made == ["plain", "pointed"], made)
check("the old process is let go", stands[0].dead)
check("it is told the device before the first line", stands[1].lines[:1] == ["D " + HEADSET], stands[1].lines)
sp.say_text("Three")
wait_for(lambda: sum(1 for x in stands[1].lines if x.startswith("S ")) == 2)
check("and not again for each line", sum(1 for x in stands[1].lines if x.startswith("D ")) == 1, stands[1].lines)
sp.set_device(SPEAKERS)
sp.say_text("Four")
wait_for(lambda: any(x == "D " + SPEAKERS for sd in stands for x in sd.lines))
check("another device is told to the same process", len(stands) == 2 and "D " + SPEAKERS in stands[1].lines, stands[1].lines)
sp.set_device("")
sp.say_text("Five")
wait_for(lambda: len(stands) == 3)
check("back to the default: the plain process again", made[-1] == "plain" and len(stands) == 3, made)
check("the pointed one is let go", stands[1].dead)
sp.say_file(os.path.join(TMP, "x.wav"))
wait_for(lambda: any(x.startswith("W ") for x in stands[2].lines))
check("a sound file goes through the same process, as a W line", "W " + os.path.join(TMP, "x.wav") in stands[2].lines, stands[2].lines)
sp.close()

stands, made = [], []
sp = VO.Speaker(spawn=plain, folders=[TMP])
sp.set_device(HEADSET)
sp.say_text("No pointed kind here")
wait_for(lambda: stands and any(x.startswith("S ") for x in stands[0].lines))
check("without a way of pointing (not Windows), the plain process is used and the device ignored",
      made == ["plain"] and not any(x.startswith("D ") for x in stands[0].lines), (made, stands[0].lines))
sp.close()

stands, made = [], []
sp = VO.Speaker(spawn=plain, folders=[TMP])
sp.spawn = None            # (spawn=None would really speak on Windows)
sp.spawn_device = None
sp.set_device(HEADSET)
check("and a Speaker that cannot speak still takes the setting", sp.device == HEADSET and sp.say_file("x.wav") is False)

print("== a device that fails to point is reported ==")
check("E D is explained", VO.explain_problem("E D Element not found").startswith("The audio device could not be used"),
      VO.explain_problem("E D Element not found"))

print("== the setting, the tab, the app ==")
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as exc:
    print("  SKIP  needs a display (%s)" % exc)
    print("\nFAILURES: %d" % len(fails))
    sys.exit(1 if fails else 0)

import overlay as OV      # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A         # noqa: E402

check("the default is the system's", A.DEFAULT_SETTINGS.get("audio_device") == "")
check("it has its note", bool(A.SETTING_TIPS.get("audio_device")))
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)


def write(**extra):
    data = {"asked_to_share": True, "tour_done": True, "voice_asked": True,
            "welcome_seen_version": A.APP_VERSION, "journal_dir": JOURNALS}
    data.update(extra)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


STATE = {}


def pump(times=3):
    for _ in range(times):
        try:
            STATE["app"].update_idletasks()
            STATE["app"].update()
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


def start(backend):
    if STATE.get("app") is not None:
        try:
            STATE["app"].destroy()
        except Exception:
            pass
    A.AUDIO_BACKEND = backend
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None
    STATE["app"] = app
    return app


def labels(page):
    out = []

    def walk(w):
        for child in w.winfo_children():
            try:
                out.append(str(child.cget("text")))
            except Exception:
                pass
            walk(child)
    walk(page)
    return out


write(audio_device=HEADSET)
app = start(FakeBackend(got))
check("the app reads the list in the background", settle_until(lambda: app.audio.ready))
win = A.SettingsWindow(app)
pump(5)
check("Output device is a choice on the Audio tab", "audio_device" in win.choices)
box, options = win.choices["audio_device"]
check("it offers the default and both devices", [n for n, _v in options] == ["System default", "Headset (USB Audio)", "Speakers (Realtek)"], options)
check("and shows the one saved", box.get() == "Headset (USB Audio)", box.get())
check("it says what it can and cannot point", any("sonar" in t.lower() and "default" in t.lower() for t in labels(win.pages["Audio"])),
      [t for t in labels(win.pages["Audio"]) if "sonar" in t.lower()])
box.set("Speakers (Realtek)")
win.save()
settle_until(lambda: json.load(open(A.SETTINGS_FILE)).get("audio_device") == SPEAKERS)
check("saved by its id", json.load(open(A.SETTINGS_FILE)).get("audio_device") == SPEAKERS)

print("== the app points the speaker ==")
app.voice.say_line = lambda *a, **k: True
app.speak("voice_test", force=True)
check("the speaker is pointed at the saved device", app.voice.device == SPEAKERS, app.voice.device)
app.settings["audio_device"] = "gone-id"
app.speak("voice_test", force=True)
check("a device that is gone: the default", app.voice.device == "", app.voice.device)
app.settings["audio_device"] = ""
app.speak("voice_test", force=True)
check("none chosen: the default", app.voice.device == "")

print("== the rig warning follows the device ==")
played = []
app.voice.say_file = lambda path: played.append(path) or True
app.settings.update({"audio_device": SPEAKERS, "rig_sound_profane": False})
app.voice.device = SPEAKERS
app.sound_alarm()
check("with a device chosen the warning's file is played through the speaker's process",
      played and played[0].endswith("rig-warning.wav"), played)
played.clear()
app.settings["audio_device"] = ""
app.voice.device = ""
app.sound_alarm()
check("with the default it is played as it always was", not played, played)

print("== a device that has gone is kept, not lost ==")
write(audio_device="gone-id")
app = start(FakeBackend(got))
settle_until(lambda: app.audio.ready)
win = A.SettingsWindow(app)
pump(5)
box, options = win.choices["audio_device"]
check("offered as not connected, and shown", options[-1] == ("Chosen device (not connected)", "gone-id")
      and box.get() == "Chosen device (not connected)", (options, box.get()))
check("a note says the default is used meanwhile", any("not connected" in t.lower() and "default" in t.lower()
                                                       for t in labels(win.pages["Audio"])), labels(win.pages["Audio"])[-8:])
win.save()
check("Save keeps it", json.load(open(A.SETTINGS_FILE)).get("audio_device") == "gone-id")

print("== where nothing can be pointed ==")
write()
app = start(AD.NoDevices())
win = A.SettingsWindow(app)
pump(5)
check("no choice is shown", "audio_device" not in win.choices)
check("and it is said plainly", any("not available" in t.lower() for t in labels(win.pages["Audio"])), labels(win.pages["Audio"])[-8:])
win.save()
check("the setting stays the default", json.load(open(A.SETTINGS_FILE)).get("audio_device", "") == "")

print("== the guide ==")
guide = open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
check("the guide says which sounds the device choice reaches and which not", "Output device" in guide and "sonar" in guide.lower())
try:
    STATE["app"].destroy()
except Exception:
    pass
print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
