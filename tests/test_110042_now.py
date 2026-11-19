"""1.10042: live status for the Radio Raxxla Twitch bot.

The plain part (nowstatus.py) and the community client's call. The switch
and the half-minute tick are checked with the app in test_110042_checks.py.

    python tests/test_110042_now.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import edonline as EDO      # noqa: E402
import nowstatus as NS      # noqa: E402
import streamout as SO      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


print("== the ranks, by name ==")
got = NS.rank_names({"Combat": 8, "Trade": 3, "Explore": 13, "Soldier": 0, "Exobiologist": 5, "CQC": 99})
check("each number is its name on that ladder", got["combat"] == "Elite" and got["trade"] == "Dealer"
      and got["exploration"] == "Elite V" and got["mercenary"] == "Defenceless"
      and got["exobiologist"] == "Taxonomist", got)
check("a number off the ladder is nothing, not a guess", got["cqc"] is None)
check("nothing from the journal yet is six empty answers",
      NS.rank_names(None) == {key: None for key, _j, _l in NS.RANKS} and len(NS.RANKS) == 6)
check("every ladder is fourteen long, Elite then Elite I to V",
      all(len(ladder) == 14 and ladder[8:] == ("Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V")
          for _k, _j, ladder in NS.RANKS))

print("== when to send ==")
check("on for the first time: now", NS.step(True, False, 0.0, 100.0) == "send")
check("then every half minute", NS.step(True, True, 100.0, 120.0) is None and NS.step(True, True, 100.0, 130.0) == "send")
check("switched off after sending: taken down", NS.step(False, True, 100.0, 105.0) == "clear")
check("off and never sent: nothing", NS.step(False, False, 0.0, 105.0) is None)

print("== the status ==")
state = SO.stream_state(cmdr="Tester", system="Ega", body="Ega 1", mined={"Platinum": 57}, seconds=83 * 60 + 12,
                        running=True, cr_hr=41200000, rigs_down=4, rig_types=["Platinum"] * 4, in_rhino=True,
                        version="1.10042")
status = NS.build(state, ship_type="Panther Clipper Mk II", ship_name="Dig Deep",
                  ranks=NS.rank_names({"Combat": 8}), version="1.10042")
check("it has the six parts and nothing else",
      sorted(status) == ["body", "edsmt", "ranks", "session", "ship", "system"], sorted(status))
check("where, as the stream card has it", status["system"] == "Ega" and status["body"] == "Ega 1")
check("the ship", status["ship"] == {"type": "Panther Clipper Mk II", "name": "Dig Deep"})
check("the session: the card's own line, tonnes, credits an hour, minutes, rigs out",
      status["session"] == {"running": True, "doing": state["doing"], "tonnes": 57,
                            "credits_per_hour": 41200000, "minutes": 83, "rigs_out": 4}, status["session"])
check("and what the card says is being done is not empty", bool(state["doing"]), state["doing"])
check("the version", status["edsmt"] == {"version": "1.10042"})
check("never a position, a bearing or a distance: each part holds only its own fields",
      set(status["ship"]) == {"type", "name"} and set(status["edsmt"]) == {"version"}
      and set(status["session"]) == {"running", "doing", "tonnes", "credits_per_hour", "minutes", "rigs_out"}
      and set(status["ranks"]) == {key for key, _j, _l in NS.RANKS}, status)
hidden = SO.stream_state(system="Ega", body="Ega 1", hide=lambda text: "", version="1.10042")
quiet = NS.build(hidden)
check("while streamer mode hides the names they are not sent", quiet["system"] is None and quiet["body"] is None)
check("nothing known is still a whole answer", NS.build(None)["session"]["running"] is False
      and NS.build(None)["ship"] == {"type": None, "name": None})

print("== the community client ==")
client = EDO.CommunityClient(EDO.Worker())
jobs = []
client.worker.submit = lambda tag, fn: jobs.append(tag)
client.configure("", "", True, True)
check("the tag is its own", EDO.NOW_TAG == NS.TAG == "now")
check("a status is sent for a commander", client.send_now("Tester", status) is True and jobs == [EDO.NOW_TAG], jobs)
check("taking it down is a send too", client.send_now("Tester", None) is True and len(jobs) == 2)
check("no commander, nothing sent", client.send_now("", status) is False and len(jobs) == 2)

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
