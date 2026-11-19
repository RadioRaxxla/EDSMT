"""1.10042 (G6): "Do you want EDSMT to speak?" - asked once, before any voice.

On a first start, and once on the first start after updating to this
version, a plain question: Yes, No or Choose a voice. It comes before any
voice is heard, the answer sets the voice setting, and it is never asked
again.

    python tests/test_110042_voiceask.py
"""
import faulthandler
import glob
import json
import os
import re
import sys
import tempfile
import time

faulthandler.dump_traceback_later(240, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-voiceask-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import voiceask as VQ      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


print("== the words ==")
check("the question, plainly", VQ.QUESTION == "Do you want EDSMT to speak?", VQ.QUESTION)
check("three answers: Yes, No, Choose a voice",
      [name for _k, name in VQ.ANSWERS] == ["Yes", "No", "Choose a voice"], VQ.ANSWERS)
check("it speaks to a commander, in UK English, with no hype",
      "CMDR" not in VQ.NOTE and "color" not in VQ.NOTE.lower())

print("== when it is asked ==")
check("a first start: asked", VQ.ask_due({}, "1.10042"))
check("a first start with the welcome due: asked", VQ.ask_due({"asked_to_share": True}, "1.10042"))
check("updating (welcome due for this version, never asked): asked",
      VQ.ask_due({"asked_to_share": True, "welcome_seen_version": "1.10041"}, "1.10042"))
check("already answered: never again",
      not VQ.ask_due({"voice_asked": True}, "1.10042")
      and not VQ.ask_due({"voice_asked": True, "welcome_seen_version": "1.10041"}, "1.10043"))
check("a start where the welcome is not due and the sharing was put: not asked (nothing new)",
      not VQ.ask_due({"asked_to_share": True, "welcome_seen_version": "1.10042"}, "1.10042"))
check("nonsense settings are a first start", VQ.ask_due(None, "1.10042"))

print("== what an answer does ==")
check("Yes: speaking on, asked", VQ.answer("yes") == {"voice_mode": True, "voice_asked": True}, VQ.answer("yes"))
check("No: speaking off, asked", VQ.answer("no") == {"voice_mode": False, "voice_asked": True}, VQ.answer("no"))
check("Choose a voice: on, asked", VQ.answer("choose") == {"voice_mode": True, "voice_asked": True})
check("a window closed with no answer: asked, the setting left as it was",
      VQ.answer("") == {"voice_asked": True} and VQ.answer(None) == {"voice_asked": True})
check("only Choose opens the Audio settings",
      VQ.opens_settings("choose") and not VQ.opens_settings("yes") and not VQ.opens_settings("no"))

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the window needs a display (%s)" % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    STATE = {"app": None}

    def write_settings(**extra):
        data = {"journal_dir": JOURNALS}
        data.update(extra)
        with open(A.SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def saved():
        with open(A.SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)

    def pump(times=3):
        app = STATE["app"]
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

    def start():
        if STATE["app"] is not None:
            try:
                STATE["app"].destroy()
            except Exception:
                pass
        app = A.EDSMT()
        app.geometry("1400x900+0+0")
        app.updates.check = lambda *args, **kwargs: None
        STATE["app"] = app
        app.said = []
        app.voice.say_line = lambda *a, **k: app.said.append(a) or True
        app.start_tour = lambda force=False: True
        return app

    def questions():
        return [w for w in STATE["app"].winfo_children()
                if isinstance(w, A.VoiceQuestionWindow) and w.winfo_exists()]

    def welcomes():
        return [w for w in STATE["app"].winfo_children()
                if isinstance(w, A.WelcomeWindow) and w.winfo_exists()]

    def button(win, text):
        found = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    if child.cget("text") == text and hasattr(child, "invoke"):
                        found.append(child)
                except Exception:
                    pass
                walk(child)
        walk(win)
        return found[0] if found else None

    print("== a first start: the question first, nothing heard ==")
    write_settings(voice_mode=True)
    app = start()
    check("the question opens", settle_until(lambda: len(questions()) == 1))
    pump(25)
    check("and no welcome is over it", not welcomes())
    check("no voice is heard while it is open (even with speaking already on)", app.said == [], app.said)
    check("it says the question", button(questions()[0], "Yes") is not None
          and button(questions()[0], "No") is not None and button(questions()[0], "Choose a voice") is not None)
    button(questions()[0], "Yes").invoke()
    check("Yes closes it, and the welcome follows", settle_until(lambda: not questions() and len(welcomes()) == 1))
    check("the answer is saved: speaking on, never asked again",
          saved().get("voice_mode") is True and saved().get("voice_asked") is True, saved())
    check("the setting in the app follows", app.settings.get("voice_mode") is True)

    print("== No ==")
    write_settings(voice_mode=True)
    app = start()
    settle_until(lambda: len(questions()) == 1)
    button(questions()[0], "No").invoke()
    settle_until(lambda: not questions())
    check("No: speaking off and kept off", saved().get("voice_mode") is False and saved().get("voice_asked") is True, saved())
    pump(40)
    check("and nothing was said", app.said == [], app.said)

    print("== Choose a voice ==")
    write_settings()
    app = start()
    settle_until(lambda: len(questions()) == 1)
    button(questions()[0], "Choose a voice").invoke()
    check("Settings opens on the Audio tab", settle_until(
        lambda: any(isinstance(w, A.SettingsWindow) and w.winfo_exists() and w.tabs.get() == "Audio"
                    for w in app.winfo_children())))
    check("speaking is on", saved().get("voice_mode") is True and saved().get("voice_asked") is True, saved())

    print("== never asked again ==")
    write_settings(voice_asked=True)
    app = start()
    pump(30)
    check("no question on the next start", not questions())
    check("the welcome is what opens", settle_until(lambda: len(welcomes()) == 1))

    print("== an update: asked once, then not ==")
    write_settings(asked_to_share=True, welcome_seen_version="1.10000", tour_done=True)
    app = start()
    check("asked after updating", settle_until(lambda: len(questions()) == 1))
    questions()[0].answer("")
    settle_until(lambda: saved().get("voice_asked") is True)
    check("closing the window with its close box counts as answered", saved().get("voice_asked") is True, saved())

    print("== a start where nothing is new asks nothing ==")
    write_settings(asked_to_share=True, welcome_seen_version=A.APP_VERSION, tour_done=True)
    app = start()
    pump(30)
    check("no question", not questions() and not welcomes())

    print("== a check that builds the main window cannot be caught by it ==")
    quiet = []
    for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        text = open(path, encoding="utf-8").read()
        if re.search(r"\bA\.EDSMT\(\)", text) and "welcome_seen_version" not in text:
            quiet.append(os.path.basename(path))
    check("every one of them already says the welcome was seen, which also skips the question", not quiet, quiet)
    try:
        STATE["app"].destroy()
    except Exception:
        pass

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
