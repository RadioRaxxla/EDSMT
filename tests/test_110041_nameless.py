"""1.10041: a find never leaves without the commander's name on it.

Every find is shared with the CMDR name. The name only ever comes from the
journal, and a journal file that carries on from an earlier part never says
who is playing - so EDSMT, started mid-session on such a part, shared finds
with no name on them. Three things put that right, each checked here:

  - the reader looks back to the part that does say, when the file it is on
    says it carries on from one;
  - a find marked before the name is known is held, on disk, and goes up by
    itself the moment the name is;
  - the map client itself will not send a find without a name.

Every commander, system and figure here is made up.

    python tests/test_110041_nameless.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-nameless-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import journal as JN      # noqa: E402
import edonline as EDO    # noqa: E402
import sharehold as SH    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def write(folder, name, events, age_s):
    """A journal file in the shape the game writes, last changed age_s ago."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "wb") as handle:
        for event in events:
            handle.write(json.dumps(event).encode("utf-8") + b"\r\n")
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))
    return path


def header(part):
    return {"timestamp": "2026-11-08T10:00:00Z", "event": "Fileheader", "part": part,
            "language": "English/UK", "Odyssey": True, "gameversion": "4.4.1.1", "build": "r1"}


def named(name):
    return [{"timestamp": "2026-11-08T10:00:05Z", "event": "Commander", "FID": "F1", "Name": name},
            {"timestamp": "2026-11-08T10:00:30Z", "event": "LoadGame", "FID": "F1", "Commander": name,
             "Ship": "Type9", "ShipID": 7, "GameMode": "Solo", "Credits": 1}]


WHERE = {"timestamp": "2026-11-08T12:00:00Z", "event": "Location", "StarSystem": "Made Up 1",
         "SystemAddress": 1, "StarPos": [0.0, 0.0, 0.0], "Body": "Made Up 1 A 2", "BodyID": 4,
         "BodyType": "Planet"}


def watcher_on(folder):
    watcher = JN.JournalWatcher(folder)
    for _ in range(4):
        watcher.poll()
    return watcher


print("== the reader looks back to the part that names the commander ==")
A = os.path.join(TMP, "a")
write(A, "Journal.2026-11-07T200000.01.log", [header(1)] + named("Old Hand") + [WHERE], 9000)
write(A, "Journal.2026-11-08T100000.01.log", [header(1)] + named("Bea Quarry") + [WHERE], 600)
second = write(A, "Journal.2026-11-08T113000.02.log", [header(2), WHERE], 60)
check("the earlier part's name, found from the part that carries on",
      JN.earlier_commander(A, second) == "Bea Quarry", JN.earlier_commander(A, second))
w = watcher_on(A)
check("EDSMT started on part 2 knows who is playing", w.cmdr == "Bea Quarry", repr(w.cmdr))
check("and where", w.system == "Made Up 1", w.system)

B = os.path.join(TMP, "b")
write(B, "Journal.2026-11-08T100000.01.log", [header(1)] + named("Bea Quarry"), 900)
write(B, "Journal.2026-11-08T113000.02.log", [header(2), WHERE], 600)
third = write(B, "Journal.2026-11-08T130000.03.log", [header(3), WHERE], 60)
check("part 3 looks back past part 2 to part 1", JN.earlier_commander(B, third) == "Bea Quarry")
check("and the reader started on part 3 has the name", watcher_on(B).cmdr == "Bea Quarry")

print("== it never borrows a name from another game session ==")
C = os.path.join(TMP, "c")
write(C, "Journal.2026-11-07T200000.01.log", [header(1)] + named("Old Hand") + [WHERE], 9000)
fresh = write(C, "Journal.2026-11-08T100000.01.log", [header(1)], 60)
check("a first part with nobody loaded yet: no name", JN.earlier_commander(C, fresh) == "")
check("the reader at the main menu has no name", watcher_on(C).cmdr == "")

D = os.path.join(TMP, "d")
write(D, "Journal.2026-11-07T200000.01.log", [header(1)] + named("Old Hand"), 9000)
write(D, "Journal.2026-11-07T213000.02.log", [header(2), WHERE], 8000)
orphan = write(D, "Journal.2026-11-08T113000.02.log", [header(2), WHERE], 60)
check("the file before is not an earlier part of this one: no name",
      JN.earlier_commander(D, orphan) == "", JN.earlier_commander(D, orphan))

E = os.path.join(TMP, "e")
alone = write(E, "Journal.2026-11-08T113000.02.log", [header(2), WHERE], 60)
check("nothing earlier to read: no name, no error", JN.earlier_commander(E, alone) == "")
check("a folder that is not there: no name, no error",
      JN.earlier_commander(os.path.join(TMP, "nowhere"), alone) == "")

F = os.path.join(TMP, "f")
big = [header(1)] + named("Bea Quarry") + [dict(WHERE, pad="x" * 400) for _ in range(4000)]
write(F, "Journal.2026-11-08T100000.01.log", big, 600)
part2 = write(F, "Journal.2026-11-08T113000.02.log", [header(2), WHERE], 60)
began = time.time()
check("a long first part is read from its top only", JN.earlier_commander(F, part2) == "Bea Quarry")
check("  and quickly", time.time() - began < 1.0, time.time() - began)
before = {name: os.path.getmtime(os.path.join(F, name)) for name in os.listdir(F)}
JN.earlier_commander(F, part2)
check("looking back changes nothing in the journal folder",
      before == {name: os.path.getmtime(os.path.join(F, name)) for name in os.listdir(F)})

G = os.path.join(TMP, "g")
write(G, "Journal.2026-11-08T100000.01.log", [header(1)] + named("Bea Quarry"), 600)
write(G, "Journal.2026-11-08T113000.02.log",
      [header(2), {"timestamp": "2026-11-08T12:10:00Z", "event": "LoadGame", "FID": "F2",
                   "Commander": "Second Seat", "Ship": "Type9", "ShipID": 1}], 60)
check("a name in the file itself is the one used", watcher_on(G).cmdr == "Second Seat")

print("== a find marked before the name is known is held ==")
HOLD = os.path.join(TMP, "hold")
os.makedirs(HOLD)
row = {"system": "Made Up 1", "planet": "A 2", "spot": "1", "type": "Platinum", "rigs": 4,
       "lat": 1.5, "lon": 2.5}
hold = SH.Hold(HOLD)
check("nothing held to begin with", hold.count == 0 and hold.take() == [])
check("one find held", hold.add([row]) == 1 and hold.count == 1)
check("the same find again is not held twice", hold.add([dict(row)]) == 0 and hold.count == 1)
hold.add([dict(row, spot="2", lat=3.0)])
check("kept on disk, in the data folder", os.path.isfile(os.path.join(HOLD, SH.FILE_NAME)))
again = SH.Hold(HOLD)
check("still held after EDSMT is closed and opened", again.count == 2, again.count)
taken = again.take()
check("taken in the order they were marked", [r["spot"] for r in taken] == ["1", "2"], taken)
check("and then nothing is held, on disk either", again.count == 0 and SH.Hold(HOLD).count == 0)
many = SH.Hold(HOLD)
many.add([dict(row, spot=str(n), lat=float(n)) for n in range(SH.MOST + 25)])
check("never more than %d held: the oldest go" % SH.MOST, many.count == SH.MOST
      and many.take()[0]["spot"] == "25")
with open(os.path.join(HOLD, SH.FILE_NAME), "w", encoding="utf-8") as fh:
    fh.write("{ not json")
check("a damaged file is an empty hold, not a crash", SH.Hold(HOLD).count == 0)
check("no folder: holds for this run, without error", SH.Hold("").add([row]) == 1)

print("== the map client will not send a find without a name ==")


class FakeWorker:
    def __init__(self):
        self.sent = []

    def submit(self, tag, job):
        self.sent.append(tag)


worker = FakeWorker()
client = EDO.CommunityClient(worker=worker)
client.configure("", enabled=True, share_name=True)
check("no name: not sent", client.upload("", [row]) is False and worker.sent == [], worker.sent)
check("spaces are not a name", client.upload("   ", [row]) is False and worker.sent == [])
check("a name: sent", client.upload("Bea Quarry", [row]) is True and worker.sent == ["share"], worker.sent)

print("== EDSMT holds, then sends ==")
import edsmt as APP    # noqa: E402


class Watcher:
    cmdr = ""


class Map:
    """Stands in for the map client: takes a chunk, or refuses the lot."""

    def __init__(self):
        self.ready, self.refuse, self.got = True, False, []

    def upload(self, cmdr, rows):
        if self.refuse or not cmdr.strip():
            return False
        self.got.append((cmdr, list(rows)))
        return True


class Stand:
    """Just enough of the app for the three methods under test."""
    hold_finds = APP.EDSMT.hold_finds
    send_held_finds = APP.EDSMT.send_held_finds
    share_imported = APP.EDSMT.share_imported

    def __init__(self, folder):
        self.settings = {"community_auto_share": True}
        self.watcher, self.community = Watcher(), Map()
        self.share_hold = SH.Hold(folder)
        self.said = []

    def say(self, text, colour=None):
        self.said.append(text)

    def trouble(self, what, exc):
        self.said.append("%s: %s" % (what, exc))


LIVE = os.path.join(TMP, "live")
os.makedirs(LIVE)
app = Stand(LIVE)
check("a find with no name yet is held, and the commander is told",
      app.hold_finds([row]) == 1 and app.share_hold.count == 1
      and "until the game says who is playing" in app.said[-1], app.said)
check("nothing is sent while the name is unknown", app.send_held_finds() == 0 and app.community.got == [])
app.watcher.cmdr = "Bea Quarry"
app.community.refuse = True
check("the map not taking it keeps the find held", app.send_held_finds() == 0 and app.share_hold.count == 1)
app.community.refuse = False
check("once the name is known the held find goes up with it",
      app.send_held_finds() == 1 and app.community.got == [("Bea Quarry", [row])], app.community.got)
check("and the hold is empty", app.share_hold.count == 0 and app.send_held_finds() == 0)
app.settings["community_auto_share"] = False
app.share_hold.add([row])
check("sharing switched off: held finds stay put", app.send_held_finds() == 0 and app.share_hold.count == 1)

print("== an import made before the game has said who is playing ==")
old = [dict(lat="1", lon=str(n), system="Made Up 1", body="A 2", location="1", commodity="Gold",
            rigs="2", density="", amount="", status="reported") for n in range(250)]
late = Stand(os.path.join(TMP, "late"))
check("nothing is sent without a name", late.share_imported(old) == 0 and late.community.got == [])
check("all 250 are held, and the commander is told", late.share_hold.count == 250
      and "250 finds" in late.said[-1], (late.share_hold.count, late.said[-1:]))
late.watcher.cmdr = "Bea Quarry"
check("with the name known they go, a hundred at a time, under it",
      late.send_held_finds() == 250 and [len(rows) for _who, rows in late.community.got] == [100, 100, 50]
      and {who for who, _rows in late.community.got} == {"Bea Quarry"},
      [(who, len(rows)) for who, rows in late.community.got])
named_app = Stand(os.path.join(TMP, "named"))
named_app.watcher.cmdr = "Bea Quarry"
check("an import with the name already known goes straight up", named_app.share_imported(old[:3]) == 3
      and named_app.share_hold.count == 0 and len(named_app.community.got) == 1, named_app.community.got)

print("== EDSMT's own wiring ==")
src = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
check("a find with no name yet goes to the hold", "self.share_hold.add(" in src)
check("held finds are sent once the name is known", "def send_held_finds(" in src and "self.share_hold.take()" in src)
check("the commander is told, in plain words", "until the game says who is playing" in src)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
