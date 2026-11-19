"""1.10042: a closed window takes its timers with it.

Tk names a callback by where it sits in memory. When a window or tab is
closed its callbacks are deleted, but a timer it had waiting is not - and
the next callback made can be given the freed name. The timer then runs
that one: a drop-down that chooses by itself, a Preview nobody pressed.
tkguard.py cancels a widget's waiting timers, and its children's, as it is
destroyed. They could only have failed.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_timers.py
"""
import faulthandler
import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk

faulthandler.dump_traceback_later(120, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import tkguard as TKG      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


root = tk.Tk()
root.withdraw()


def pump(seconds=0.1):
    until = time.time() + seconds
    while True:
        root.update_idletasks()
        root.update()
        if time.time() >= until:
            break
        time.sleep(0.005)


def settle_until(cond, seconds=3.0):
    """Wait for `cond`, up to a deadline - never a fixed number of loops."""
    until = time.time() + seconds
    while time.time() < until:
        if cond():
            return True
        pump(0.02)
    return bool(cond())


def waiting():
    return list(root.tk.splitlist(root.tk.call("after", "info")))


def script_of(job):
    return root.tk.splitlist(root.tk.call("after", "info", job))[0]


print("== the hazard, as the toolkit leaves it ==")
check("nothing is guarded until it is asked for", not TKG.installed())
frame = tk.Frame(root)
hits = []
job = frame.after(120, lambda: hits.append("its own"))
name = script_of(job)
check("a timer made with a lambda is filed under a name ending <lambda>", name.endswith("<lambda>"), name)
frame.destroy()
check("the frame is closed and its timer is still waiting", job in waiting(), waiting())
# The next callback made is given the freed name. Made to happen here; in
# the app it happens by chance, whenever the freed address is used again.
root.tk.createcommand(name, lambda *args: hits.append("someone else's"))
settle_until(lambda: hits)
check("when it fires it runs whatever has that name now", hits == ["someone else's"], hits)
root.tk.deletecommand(name)

print("== with the guard ==")
TKG.install()
check("installed", TKG.installed())
TKG.install()
check("asking twice installs it once", tk.BaseWidget.destroy.__wrapped__ is TKG.ORIGINAL)
frame = tk.Frame(root)
child = tk.Label(frame)
grandchild = tk.Label(child)
other = tk.Frame(root)
hits = []
mine = frame.after(120, lambda: hits.append("frame"))
inner = child.after(120, lambda: hits.append("child"))
deep = grandchild.after_idle(lambda: hits.append("grandchild"))
theirs = other.after(120, lambda: hits.append("other"))
roots = root.after(120, lambda: hits.append("root"))
freed = [script_of(job) for job in (mine, inner, deep)]
frame.destroy()
left = waiting()
check("closing a frame cancels its timers", mine not in left, left)
check("and those of everything inside it, however deep", inner not in left and deep not in left, left)
check("and nobody else's", theirs in left and roots in left, left)
for stale in freed:
    root.tk.createcommand(stale, lambda *args: hits.append("someone else's"))
settle_until(lambda: len(hits) >= 2)
pump(0.3)
check("so nothing runs under a freed name", sorted(hits) == ["other", "root"], hits)
for stale in freed:
    root.tk.deletecommand(stale)
check("the frame and what was in it are gone, as before",
      not int(root.tk.call("winfo", "exists", str(frame)))
      and not int(root.tk.call("winfo", "exists", str(grandchild)))
      and int(root.tk.call("winfo", "exists", str(other))))

print("== by hand, and when things go wrong ==")
panel = tk.Frame(root)
one = panel.after(5000, lambda: None)
two = panel.after(5000, lambda: None)
check("cancel_timers says how many it cancelled", TKG.cancel_timers(panel) == 2 and one not in waiting()
      and two not in waiting())
check("with nothing waiting it cancels nothing", TKG.cancel_timers(panel) == 0)
panel.destroy()
check("a widget already gone is not an error", TKG.cancel_timers(panel) == 0)


class Awkward(tk.Frame):
    def destroy(self):
        super().destroy()
        raise RuntimeError("a fault in a window's own closing")


awkward = Awkward(root)
try:
    awkward.destroy()
except RuntimeError:
    pass
later = tk.Frame(root)
job = later.after(5000, lambda: None)
later.destroy()
check("a window whose closing raises does not switch the guard off for the next", job not in waiting(), waiting())

print("== the app asks for it as it loads ==")
env = dict(os.environ, LOCALAPPDATA=tempfile.mkdtemp(prefix="edsmt-timers-"), PYTHONIOENCODING="utf-8")
out = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r); import edsmt, tkguard; print('guarded' if tkguard.installed() else 'not guarded')" % REPO],
    capture_output=True, text=True, env=env, timeout=100)
check("importing the app installs the guard", out.stdout.strip().endswith("guarded")
      and "not guarded" not in out.stdout, (out.stdout[-200:], out.stderr[-300:]))

print("== where there are no real widgets ==")
out = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r); import _ctkstub, tkguard; "
     "print(tkguard.install(), tkguard.installed()); import edsmt; print('loaded')"
     % (REPO, os.path.join(HERE, "stubs"))],
    capture_output=True, text=True, env=env, timeout=100)
check("under a stand-in toolkit the guard does nothing, and says so",
      out.stdout.split()[:2] == ["False", "False"], (out.stdout[-200:], out.stderr[-300:]))
check("and the app still loads there, which the headless checks rely on",
      out.stdout.strip().endswith("loaded"), (out.stdout[-200:], out.stderr[-400:]))

root.destroy()
print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
