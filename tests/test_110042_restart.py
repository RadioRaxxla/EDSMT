"""1.10042: the one-file program restarts itself cleanly.

Reported from the portable file: after choosing a theme and "Save and
restart now", Windows said "Failed to remove temporary directory ...
_MEI...", and the copy that opened had no voice and could not reach the
community map ("No such file or directory ... base_library.zip").

The one-file program unpacks itself into a temporary folder and tells
anything it starts where that folder is. A new copy started that way used
the closing copy's folder, which was then removed from under it. The
packager's own answer is a word in the new copy's environment that tells
it to unpack for itself; relaunch.py says that word for the restart and
for the update, and edsmt.py starts both through it.

    python tests/test_110042_restart.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import relaunch as RL      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


print("== the environment a new copy is started with ==")
UNPACKED = os.path.join("C:\\", "Users", "Dave", "AppData", "Local", "Temp", "_MEI00005b742")
mine = {"PATH": "C:\\Windows", "LOCALAPPDATA": "C:\\Users\\Dave\\AppData\\Local",
        "TCL_LIBRARY": os.path.join(UNPACKED, "_tcl_data"),
        # Windows does not care about letter case in a path; Linux does.
        "TK_LIBRARY": os.path.join(UNPACKED.upper() if os.name == "nt" else UNPACKED, "_tk_data"),
        "_MEIPASS2": UNPACKED}
before = dict(mine)
env = RL.fresh_environment(mine, unpacked=UNPACKED)
check("it tells the new copy to unpack for itself", env.get("PYINSTALLER_RESET_ENVIRONMENT") == "1", env)
check("everything else the commander's PC set is kept",
      env["PATH"] == "C:\\Windows" and env["LOCALAPPDATA"] == mine["LOCALAPPDATA"], env)
check("nothing in it points into the closing copy's folder",
      "TCL_LIBRARY" not in env and "TK_LIBRARY" not in env and "_MEIPASS2" not in env, env)
check("the running copy's own environment is not touched", mine == before)
env = RL.fresh_environment(mine, unpacked="")
check("run from source there is no such folder, and nothing is dropped",
      env["TCL_LIBRARY"] == mine["TCL_LIBRARY"] and env["PYINSTALLER_RESET_ENVIRONMENT"] == "1", env)
check("with nothing passed it reads the real environment",
      RL.fresh_environment().get("PATH") == os.environ.get("PATH"))
check("and finds the unpack folder for itself", RL.unpack_folder() == getattr(sys, "_MEIPASS", ""))

print("== starting it ==")
calls = []


def fake(command, **options):
    calls.append((command, options))
    return "started"


got = RL.start(["EDSMT.exe"], popen=fake, environ=mine, unpacked=UNPACKED, windows=True)
command, options = calls[-1]
check("the program asked for is the one started", got == "started" and command == ["EDSMT.exe"], calls[-1])
check("with the clean environment", options["env"].get("PYINSTALLER_RESET_ENVIRONMENT") == "1"
      and "TCL_LIBRARY" not in options["env"], options.get("env"))
check("as a program of its own on Windows, so closing this copy does not take it down",
      options["creationflags"] == 0x00000008 | 0x00000200 and options["close_fds"] is True, options)
RL.start(["./EDSMT"], popen=fake, environ=mine, unpacked="", windows=False)
check("and with no Windows flags anywhere else", calls[-1][1]["creationflags"] == 0, calls[-1][1])


def refuses(command, **options):
    raise OSError("no such program")


try:
    RL.start(["nothing.exe"], popen=refuses, environ=mine, unpacked="", windows=True)
    raised = False
except OSError:
    raised = True
check("a program that cannot be started is the caller's to report, as before", raised)

print("== the app starts its restart and its update this way ==")
source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
check("the restart", "RL.start(relaunch)" in source)
check("the update: Setup for an installed copy, the new file for a portable one", "RL.start(command)" in source)
check("and neither starts a program any other way",
      "subprocess.Popen(relaunch" not in source and "subprocess.Popen(command" not in source)
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    text = open(os.path.join(REPO, "build", spec), encoding="utf-8").read()
    check("%s names the module" % spec, '"relaunch"' in text)
module = open(os.path.join(REPO, "relaunch.py"), encoding="utf-8").read()
check("the module imports no window", "import edsmt" not in module and "tkinter" not in module)

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
