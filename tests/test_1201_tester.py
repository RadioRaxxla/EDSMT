"""1.201: what 2020HeinSite found in 1.2 (his notes of 21 and 24 Nov).

- "Show did nothing" on the Visited, not updated list. Show now opens My
  sites on that deposit - its card says where it is, on any body - and picks
  it on the main map when it is on the body you are on.
- A depleted deposit "showed differently": a hollow ring and nothing to say
  why. Its label now says DEPLETED and the day it was first marked, on the
  map and in the deposit list, until somebody says it is back.
- MINED OUT and Worked out confused him. The names now, from 25 Nov: the one
  for a deposit is "Deposit depleted", the one for a whole signal is
  "Location depleted".
- The Visited list now says in plain words what each button does.

    python tests/test_1201_tester.py
"""
import faulthandler
import io
import json
import os
import re
import sys
import tempfile
import time
import types

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-tester1201-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import regrowth as RG     # noqa: E402
import recheck as RC      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    return io.open(os.path.join(REPO, *parts), encoding="utf-8").read()


NOV21 = time.mktime((2026, 11, 21, 2, 0, 0, 0, 0, 0)) - time.timezone

print("== the depleted tag ==")
tag = getattr(RG, "tag", None)
check("regrowth.tag exists", callable(tag))
if callable(tag):
    row = {"amount": "Depleted", "depleted_at": RG.stamp(NOV21)}
    check("DEPLETED and the day it was first marked", tag(row) == "DEPLETED 21 Nov", tag(row))
    check("a deposit that is not depleted has none", tag({"amount": "High"}) == "")
    check("depleted with no date is still said", tag({"amount": "Depleted"}) == "DEPLETED")
    stamped = {"amount": "Depleted", "notes": "Mined 21/11/2026 02:05"}
    check("an older record's MINED stamp gives the day", tag(stamped) == "DEPLETED 21 Nov", tag(stamped))

print("== the names ==")
check("the overlay asks with the new name", RC.ASK == "Still there? UPDATE or DEPOSIT DEPLETED", RC.ASK)
said = " ".join([RC.ASK, RC.left_line("Gold") if hasattr(RC, "left_line") else "", RC.HOWTO_WORDS])
check("nothing the overlay or the help says names MINED OUT or Worked out",
      "MINED OUT" not in said and "Mined out" not in said and "Worked out" not in said, said)
guide = read("docs", "GUIDE.md")
check("the GUIDE names Deposit depleted and Location depleted",
      "**Deposit depleted**" in guide and "**Location depleted**" in guide)
check("and no longer MINED OUT, Worked out or Mark depleted",
      not re.search(r"MINED OUT|\*\*Worked out\*\*|Mark depleted|Mined out or Skip", guide),
      re.findall(r".{30}(?:MINED OUT|\*\*Worked out\*\*|Mark depleted).{20}", guide))
# The page's own words only. Between the WHATSNEW markers are the patch
# notes, which BUILD.bat writes there: after any build of this version they
# name the old words to say they went, and that failed this check on the
# second build of the same tree.


def own_words(page):
    return re.sub(r"<!--WHATSNEW-->.*?<!--/WHATSNEW-->", "", page, flags=re.S)


check("the download page too", "MINED OUT" not in own_words(read("site", "index.html")))
check("the patch notes on it may name the old words",
      "MINED OUT" not in own_words("a<!--WHATSNEW-->\nMINED OUT is now DEPOSIT DEPLETED\n<!--/WHATSNEW-->b")
      and "MINED OUT" in own_words("MINED OUT<!--WHATSNEW-->x<!--/WHATSNEW-->"))
src = read("edsmt.py")
for old in ('text="MINED OUT"', 'text="Worked out"', '("Mark depleted"', '("Mined out", "mined")'):
    check("no button reads %s" % old, old not in src)

print("== INSTALL UPDATE when Windows blocks the new installer ==")
import relaunch as RL     # noqa: E402
check("Smart App Control's refusal is known", RL.blocked(OSError(0, "blocked")) is False
      and RL.blocked(type("E", (OSError,), {"winerror": 4551})()) is True)
check("the app says so and opens the download page",
      "RL.blocked(exc)" in src and "Smart App Control" in src.split("def install_update", 1)[1][:4000]
      and "self.open_download_page()" in src.split("RL.blocked(exc)", 1)[1][:600])

# A window can be made: Windows always has a display, and Linux one when
# the suite runs under xvfb-run. (Asking the environment for DISPLAY alone
# skipped every window check on Windows.)
HAVE_DISPLAY = False
try:
    import tkinter as _tk
    _probe = _tk.Tk()
    _probe.destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    print("  SKIP  the window checks need a display (%s)" % _exc)
if HAVE_DISPLAY:
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION,
                   "journal_dir": JOURNALS, "tour_done": True}, _f)

    class FakeCommunity:
        ready = can_read = True

        def __getattr__(self, name):
            return lambda *args, **kwargs: True

    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    def buttons(widget):
        out = []
        for child in widget.winfo_children():
            if isinstance(child, A.ctk.CTkButton):
                out.append(str(child.cget("text")))
            out.extend(buttons(child))
        return out

    pump()
    R = 1_000_000.0
    app.here = lambda: ("Ega", "Ega 1")
    app.store.set_location("Ega", "Ega 1", "1", lat=10.0, lon=20.0, radius_m=R)
    app.watcher.cmdr = "CMDR Hein"
    app.community = FakeCommunity()
    app.say = lambda text, colour=None, *a, **k: None
    app.flash = lambda *a, **k: True
    app.speak = lambda *a, **k: True
    app.game = types.SimpleNamespace(
        has_position=True, in_srv=True, lat=10.0, lon=20.0, radius_m=R, heading=0.0,
        detected_type="", detected_density="", target_signal="", landed=False,
        body_profile=lambda *a, **k: {"planet_class": "", "gravity": 0, "temperature_k": 0, "volcanism": ""},
        mining_signals=lambda: 0)

    print("== the main window's buttons ==")
    names = buttons(app)
    check("Deposit depleted and Location depleted are there",
          "DEPOSIT DEPLETED" in names and "Location depleted" in names,
          [n for n in names if "epleted" in n or "out" in n.lower()])
    check("MINED OUT and Worked out are not", "MINED OUT" not in names and "Worked out" not in names)
    check("My sites' card says Deposit depleted", "Deposit depleted" in [n for n, _t in A.CARD_BUTTONS])

    print("== a depleted deposit says so on the map ==")
    app.store.deposits[:] = []
    near = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Periclase dunite",
                                 rigs="3", density="High", amount="High", lat="9.98", lon="20.0")
    app.selected = near
    app.mark_mined()
    app.selected = None
    app.on_pick(None)
    app.redraw()
    pump(2)
    texts = [app.plan.itemcget(i, "text") for i in app.plan.find_all() if app.plan.type(i) == "text"]
    mine = [t for t in texts if "Periclase" in t]
    today = time.strftime("%d %b", time.gmtime()).lstrip("0")
    check("its label says DEPLETED and the day", mine and ("DEPLETED " + today) in mine[0], (mine, today))
    app.refresh_deposits()
    pump(2)
    listed = buttons(app.deposit_list)
    check("the deposit list says depleted and the day, not mined out",
          any(("depleted " + today) in t for t in listed) and not any("mined out" in t for t in listed),
          listed)

    print("== Show on the Visited list ==")
    app.store.deposits[:] = []
    here = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Rhodplumsite",
                                 rigs="1", density="Medium", amount="High", lat="10.001", lon="20.0")
    far = app.store.add_deposit(system="Synuefai", body="Synuefai A 2", location="10", commodity="Rhodplumsite",
                                rigs="1", density="Low", amount="High", lat="-38.67", lon="28.77")
    app.visits.add(here["id"], time.time())
    app.visits.add(far["id"], time.time())
    window = app.show_visited_list()
    pump(3)
    check("the list opens", window is not None and window.winfo_exists())
    note = window.note.cget("text")
    check("it says plainly what each button does",
          all(w in note for w in ("Still there", "Deposit depleted", "Skip", "Show")), note)
    check("its answers read Still there, Deposit depleted, Skip and Show",
          set(window.button_texts()) == {"Show", "Still there", "Deposit depleted", "Skip"},
          window.button_texts())
    window.show(far["id"])
    pump(3)
    sites = getattr(app, "sites_window", None)
    shown = getattr(sites, "_card_row", None) if sites is not None else None
    check("Show on another body opens My sites with that deposit's card",
          sites is not None and sites.winfo_exists() and shown and shown.get("id") == far["id"], shown)
    window.show(here["id"])
    pump(3)
    shown = getattr(getattr(app, "sites_window", None), "_card_row", None)
    check("Show on this body: its card in My sites", shown and shown.get("id") == here["id"], shown)
    check("and picked on the main map", (app.selected or {}).get("id") == here["id"]
          and app.plan.selected_id == here["id"], (app.selected or {}).get("id"))
    check("it stays on the list", here["id"] in app.visits.ids())
    window.answer(here["id"], "mined")
    pump(2)
    row = [d for d in app.store.deposits if d["id"] == here["id"]][0]
    check("Deposit depleted on the list marks it Depleted", RG.depleted(row), row.get("amount"))
    try:
        app.destroy()
    except Exception:
        pass

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
