"""1.10042: the stream card says what you are doing now.

Reported while live: the OBS card read "Not mining yet" with four rigs down
and working, because the line waited for the first tonne to be refined.

Rigs down on a deposit are mining it from the moment they go down: the card
says "Mining Iridium" at once, with how many rigs. In the Rhino with no rig
down it says "Surveying". Out of the Rhino with nothing down it says
nothing. The same line goes to Discord's Rich Presence and into the state
other tools read.

    python tests/test_110042_doing.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import streamout as SO       # noqa: E402
import richpresence as RP    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


print("== the line ==")
check("rigs down on a deposit: mining it, before any tonne",
      SO.doing_now(rig_types=["Iridium"] * 4, rigs_down=4, in_rhino=True) == "Mining Iridium",
      SO.doing_now(rig_types=["Iridium"] * 4, rigs_down=4, in_rhino=True))
check("two kinds of ground: both, the one with more rigs first",
      SO.doing_now(rig_types=["Serendibite", "Thortveitite", "Thortveitite", "thortveitite"], rigs_down=4)
      == "Mining Thortveitite, Serendibite",
      SO.doing_now(rig_types=["Serendibite", "Thortveitite", "Thortveitite", "thortveitite"], rigs_down=4))
check("what the rigs are on, not the by-products that come up with it",
      SO.doing_now(mined={"Gold": 9, "Iridium": 3}, rig_types=["Iridium"], rigs_down=1) == "Mining Iridium")
check("rigs down on ground nobody named: what has been refined says",
      SO.doing_now(mined={"Platinum": 5}, rig_types=["", None], rigs_down=2) == "Mining Platinum")
check("rigs down and nothing known at all: still mining",
      SO.doing_now(rig_types=[], rigs_down=3) == "Mining", SO.doing_now(rig_types=[], rigs_down=3))
check("with the rigs still mining while you are in the ship: mining",
      SO.doing_now(rig_types=["Iridium"], rigs_down=1, in_rhino=False) == "Mining Iridium")
check("in the Rhino with no rig down: surveying", SO.doing_now(in_rhino=True) == "Surveying")
check("even with tonnes aboard from earlier", SO.doing_now(mined={"Iridium": 40}, in_rhino=True) == "Surveying")
check("out of the Rhino with nothing down: nothing to say", SO.doing_now() == ""
      and SO.doing_now(mined={"Iridium": 40}) == "")
check("rubbish in is nothing out, never a fault",
      SO.doing_now(mined="x", rig_types=7, rigs_down="lots", in_rhino=None) == "")

print("== in the state the pages and other tools read ==")
state = SO.stream_state(cmdr="CMDR Cee", system="Ega", body="Ega 1", mined={}, running=True,
                        rigs_down=4, rig_types=["Thortveitite", "Thortveitite", "Thortveitite", "Serendibite"],
                        in_rhino=True)
check("the line is there", state.get("doing") == "Mining Thortveitite, Serendibite", state.get("doing"))
check("what is being mined is known before the first tonne", state["mining"] == ["Thortveitite", "Serendibite"],
      state["mining"])
check("the tonnes are still the tonnes", state["tonnes"] == [] and state["tonnes_total"] == 0)
check("the document's shape number has not moved: a new field is not a new shape", state["schema"] == 1)
older = SO.stream_state(mined={"Platinum": 34, "Osmium": 6}, running=True, rigs_down=4)
check("a caller that does not say what the rigs are on gets what it got before",
      older["mining"] == ["Platinum", "Osmium"] and older["doing"] == "Mining Platinum, Osmium", older)
check("surveying", SO.stream_state(in_rhino=True)["doing"] == "Surveying")
check("nothing", SO.stream_state()["doing"] == "" and SO.stream_state(mined={"Gold": 3})["doing"] == "")

print("== the card ==")
page = SO.viewer_page() if hasattr(SO, "viewer_page") else ""
source = open(os.path.join(REPO, "streamout.py"), encoding="utf-8").read()
check("it never says 'Not mining yet'", "Not mining yet" not in source)
paint = source.split('_VIEWER_PAINT = """')[1].split('"""')[0]
check("it shows the line the state gives", "s.doing" in paint)
check("with how many rigs are down", "rigs_down" in paint and "rig" in paint)
check("and leaves the line out when there is nothing to say", "if (doing)" in paint)

print("== Discord's Rich Presence says the same ==")
act = RP.activity(state, 1000.0)
check("mining, at once", act["details"] == "Mining Thortveitite, Serendibite", act.get("details"))
check("with the rigs", "4 rigs down" in str(act.get("state") or ""), act)
check("surveying", RP.activity(SO.stream_state(in_rhino=True, running=False), 1000.0)["details"] == "Surveying")
check("a state from before this version still reads",
      RP.activity({"session": {"running": True}, "mining": ["Gold"]}, 1000.0)["details"] == "Mining Gold"
      and RP.activity({"session": {"running": True}}, 1000.0)["details"] == "Rhino session"
      and RP.activity({}, 1000.0)["details"] == "On the surface")

print("== the app says what the rigs are on, and whether you are in the Rhino ==")
app = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
now = app.split("    def stream_now(self, now=None):")[1].split("\n    def ")[0]
check("what each rig is on", "rig_types=" in now)
check("in the Rhino or not", "in_rhino=" in now)
doc = open(os.path.join(REPO, "docs", "LOCAL-DATA.md"), encoding="utf-8").read()
check("the field is in the document other tools are written from", "| `doing` |" in doc)

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
