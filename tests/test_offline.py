"""No check reaches the internet (1.10042).

run_all.py starts every check with tests/offline on the module path, and the
sitecustomize.py there lets a check connect to this machine only. BUILD.bat
runs the checks on a PC where the community map answers, and a check that
had put its own figures in place had them replaced by the map's.

    python tests/test_offline.py
"""
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "offline")
fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def child(code):
    env = dict(os.environ)
    env["PYTHONPATH"] = GUARD + os.pathsep + env.get("PYTHONPATH", "")
    done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    return done.stdout + done.stderr


print("== the guard ==")
check("it is there", os.path.isfile(os.path.join(GUARD, "sitecustomize.py")))
# 192.0.2.1 is an address kept for examples: nothing answers there, so a
# check that is not refused would only wait and time out.
away = child("import socket\ns = socket.socket()\ns.settimeout(5)\ntry:\n    s.connect(('192.0.2.1', 80))\n"
             "    print('CONNECTED')\nexcept OSError as exc:\n    print('REFUSED', exc)\n")
check("a connection off this machine is refused at once, and says why",
      "REFUSED" in away and "test run" in away and "CONNECTED" not in away, away)
web = child("import urllib.request, urllib.error\ntry:\n    urllib.request.urlopen('https://192.0.2.1/x', timeout=5)\n"
            "    print('OPENED')\nexcept (urllib.error.URLError, OSError) as exc:\n    print('REFUSED', exc)\n")
check("a web request is refused the same way", "REFUSED" in web and "test run" in web, web)
tried = child("import socket\ns = socket.socket()\ns.settimeout(5)\nprint('CODE', s.connect_ex(('192.0.2.1', 80)))\n")
check("and the kind of connect that answers with a number says no route", "CODE 10065" in tried, tried)

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(1)
port = listener.getsockname()[1]
near = child("import socket\ns = socket.socket()\ns.settimeout(5)\ns.connect(('127.0.0.1', %d))\nprint('LOCAL OK')\n" % port)
listener.close()
check("a connection to this machine goes through", "LOCAL OK" in near, near)

print("== every check is started behind it ==")
runner = open(os.path.join(HERE, "run_all.py"), encoding="utf-8").read()
check("run_all.py puts the guard on the module path of every check",
      'os.path.join(HERE, "offline")' in runner and '"PYTHONPATH"' in runner)
if os.environ.get("EDSMT_REPO"):
    # Started by run_all.py: this very check is behind the guard.
    module = sys.modules.get("sitecustomize")
    check("this check was started behind it", bool(getattr(module, "GUARDED", False)),
          os.environ.get("PYTHONPATH", ""))
else:
    print("  (run by itself: run_all.py is what starts a check behind the guard)")

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
