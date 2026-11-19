"""1.10042: the program file an update replaced is kept as one ".previous"
copy beside the new one, and Help > "Go back to the previous version" shows
when there is one (portable build). The installed build is not covered: Setup
puts down a folder, and keeping the old folder is not safe from here.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_rollback.py
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
TMP = tempfile.mkdtemp(prefix="edsmt-rb42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import relaunch as RL   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


def put(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


def get(path):
    with open(path, "rb") as handle:
        return handle.read()


folder = os.path.join(TMP, "portable")
os.makedirs(folder)
exe = os.path.join(folder, "EDSMT.exe")
new1, new2 = os.path.join(TMP, "n1.exe"), os.path.join(TMP, "n2.exe")
put(exe, b"v1")
put(new1, b"v2")
put(new2, b"v3")

print("== an update keeps the file it replaces ==")
check("nothing kept to begin with", not RL.has_previous(exe))
RL.put_new(new1, exe)
check("the new program is in place", get(exe) == b"v2")
check("the old one is kept as .previous", get(exe + ".previous") == b"v1" and RL.has_previous(exe))
check("nothing is left as .old", not os.path.exists(exe + ".old"))
RL.put_new(new2, exe)
check("a second update keeps only the one before it", get(exe) == b"v3" and get(exe + ".previous") == b"v2"
      and sorted(os.listdir(folder)) == ["EDSMT.exe", "EDSMT.exe.previous"], os.listdir(folder))

print("== a copy that fails changes nothing ==")
import shutil   # noqa: E402
real = shutil.copy2
shutil.copy2 = lambda a, b: (_ for _ in ()).throw(OSError("disk full"))
try:
    RL.put_new(new1, exe)
    raised = False
except OSError:
    raised = True
shutil.copy2 = real
check("the old program is back and the kept one untouched", raised and get(exe) == b"v3"
      and get(exe + ".previous") == b"v2", os.listdir(folder))

print("== going back ==")
check("going back puts the kept file in place", RL.go_back(exe) == exe and get(exe) == b"v2")
check("the one it replaced is set aside to be tidied", get(exe + ".old") == b"v3")
check("no previous is kept after going back", not RL.has_previous(exe))
try:
    RL.go_back(exe)
    check("going back with none kept says so", False)
except FileNotFoundError:
    check("going back with none kept says so", True)
check("the file is still there after that", get(exe) == b"v2")
put(exe + ".previous", b"v1")
real_replace = os.replace
calls = []


def flaky(a, b):
    calls.append((a, b))
    if len(calls) == 2:
        raise OSError("locked")
    return real_replace(a, b)


os.replace = flaky
try:
    RL.go_back(exe)
    failed = False
except OSError:
    failed = True
os.replace = real_replace
check("a swap that fails half way puts the running file back", failed and get(exe) == b"v2"
      and get(exe + ".previous") == b"v1", os.listdir(folder))

print("== the app: Help's entry and the click ==")
import edsmt as A   # noqa: E402


class Menu:
    def __init__(self):
        self.items = [{"label": "Welcome"}, {"label": "Report a bug"}]

    def index(self, what):
        return len(self.items) - 1 if self.items else None

    def entrycget(self, i, key):
        return self.items[i][key]

    def delete(self, i):
        del self.items[i]

    def add_command(self, label, command):
        self.items.append({"label": label, "command": command})


class Fake:
    def go_back_to_previous(self):
        return None

    said = []
    closed = []

    def say(self, text, colour=None):
        self.said.append(text)

    def _save_on_exit(self):
        pass

    def on_close(self):
        self.closed.append(True)


app = Fake()
app.help_menu = Menu()
real_kind, real_exe = A.build_kind, sys.executable
sys.executable = exe
A.build_kind = lambda platform=None: "portable"
check("shown when a previous file is kept", A.EDSMT.refresh_go_back_item(app) is True
      and app.help_menu.items[-1]["label"] == "Go back to the previous version")
A.EDSMT.refresh_go_back_item(app)
check("not added twice", [i["label"] for i in app.help_menu.items].count("Go back to the previous version") == 1)
launched = []
real_start = RL.start
RL.start = lambda command, **kw: launched.append(command) or object()
A.release_single_instance = lambda: None
declined = A.EDSMT.go_back_to_previous(app, ask=lambda text: False)
check("asked first; no is no change", declined is False and get(exe) == b"v2" and not launched)
done = A.EDSMT.go_back_to_previous(app, ask=lambda text: True)
check("yes goes back, starts that program and closes", done is True and get(exe) == b"v1"
      and launched == [[exe]] and app.closed == [True], (launched, app.closed))
RL.start = real_start
check("gone from Help once nothing is kept", A.EDSMT.refresh_go_back_item(app) is False
      and not any(i["label"] == "Go back to the previous version" for i in app.help_menu.items))
A.build_kind = lambda platform=None: "installed"
put(exe + ".previous", b"v0")
check("the installed build never shows it", A.EDSMT.refresh_go_back_item(app) is False)
check("and the click does nothing there", A.EDSMT.go_back_to_previous(app, ask=lambda t: True) is None
      or "no previous version" in app.said[-1], app.said[-1:])
A.build_kind, sys.executable = real_kind, real_exe

print("== wiring ==")
src = read("edsmt.py")
check("Help builds its entry when it opens", "self.refresh_go_back_item()" in src)
check("the update puts the file through relaunch", "return RL.put_new(new_exe)" in src)
check("the guide says it", "go back to the previous version" in read("docs", "GUIDE.md").lower())
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
