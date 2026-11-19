"""1.10042: "Last there" is the day you were there, not the day of an import.

Reported by a tester: after an import, My sites said "today" for every
site, including one last mined two days before. An import stamped every
signal it made with the moment it ran, and My sites took the newest date
on a site whatever had written it.

Now an import is not a visit. A signal an import makes takes the date in
what was imported, or none; a row an import wrote never counts the moment
it was written; and the last tonne refined on a deposit does count. Records
already on a disk are read the same way and are not rewritten.

    python tests/test_110042_lastthere.py
"""
import calendar
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(HERE, "stubs"))
# The app is loaded further down: its data folder is moved first, so this
# never reads or writes a real commander's records.
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="edsmt-lastthere-data-")

import survey as SV        # noqa: E402
import importers as IMP    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def fresh(name):
    return SV.Survey(tempfile.mkdtemp(prefix="edsmt-lastthere-%s-" % name))


def last(store, body, signal):
    for site in store.sites():
        if (site["body"], site["signal"]) == (body, str(signal)):
            return site["last"]
    return None


def utc(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


RADIUS = 1000000.0
TODAY = SV.utc_now()[:10]

print("== logging a signal yourself is being there ==")
store = fresh("own")
row = store.set_location("Ega", "Ega 1", "1", lat=10.0, lon=20.0, radius_m=RADIUS)
check("a signal you log is dated now", row["recorded"][:10] == TODAY, row["recorded"])
row["recorded"] = "2026-10-01T09:00:00Z"
store.set_location("Ega", "Ega 1", "1", commodities=["Iridium"])
check("and logging it again moves the date on", store.location("Ega", "Ega 1", "1")["recorded"][:10] == TODAY)
check("My sites says so", (last(store, "Ega 1", "1") or "")[:10] == TODAY, last(store, "Ega 1", "1"))

print("== an import says when, or says nothing ==")
store = fresh("given")
row = store.set_location("Ega", "Ega 2", "4", notes="Imported from a file",
                         recorded="2026-11-10T20:15:00Z")
check("a signal made with a date keeps that date", row["recorded"] == "2026-11-10T20:15:00Z", row["recorded"])
row = store.set_location("Ega", "Ega 2", "5", notes="Imported from a file", recorded="")
check("a signal made with no date has none, rather than today", row["recorded"] == "", row["recorded"])
mine = store.set_location("Ega", "Ega 2", "6", lat=1.0, lon=1.0, radius_m=RADIUS)
mine["recorded"] = "2026-09-09T09:09:09Z"
store.set_location("Ega", "Ega 2", "6", notes="Imported from a file", recorded="2026-11-10T20:15:00Z")
check("a signal you already held keeps its own date", store.location("Ega", "Ega 2", "6")["recorded"]
      == "2026-09-09T09:09:09Z", store.location("Ega", "Ega 2", "6")["recorded"])

print("== the import itself ==")
CSV = ("System,Body,LocationSignalNumber,Commodity,RigCount,MineralAmount,Density,"
       "MarkerLatitude,MarkerLongitude,PlanetRadiusKm,MarkerCreatedUtc\n"
       "HR 8970,HR 8970 3 a,2,Iridium,4,High,High,10.0,20.0,1000,2026-11-10T19:40:00Z\n"
       "HR 8970,HR 8970 3 a,2,Iridium,4,High,High,10.2,20.2,1000,2026-11-08T12:00:00Z\n"
       "Col 285,Col 285 4,7,Gold,3,Low,Low,3.0,3.0,1000,\n")
store = fresh("import")
plan = IMP.make_plan(IMP.read_text(CSV), store)
done = IMP.apply(plan, store, tempfile.mkdtemp(prefix="edsmt-lastthere-backup-"))
check("three finds and two signals come in", (done["ok"], done["taken"], done["signals"]) == (True, 3, 2), done)
signal = store.location("HR 8970", "HR 8970 3 a", "2")
check("the signal takes the newest date in what was imported, not today",
      signal["recorded"] == "2026-11-10T19:40:00Z", signal["recorded"])
check("a signal whose finds carry no date has none",
      store.location("Col 285", "Col 285 4", "7")["recorded"] == "", store.location("Col 285", "Col 285 4", "7"))
check("My sites: last there is the date in the file", last(store, "HR 8970 3 a", "2") == "2026-11-10T19:40:00Z",
      last(store, "HR 8970 3 a", "2"))
check("My sites: a site known only from an undated import has no date", last(store, "Col 285 4", "7") == "",
      last(store, "Col 285 4", "7"))
sites = store.sites()
check("and it lists below the sites with one", [s["body"] for s in sites] == ["HR 8970 3 a", "Col 285 4"],
      [s["body"] for s in sites])

print("== records an earlier import already wrote ==")
store = fresh("old")
came = calendar.timegm((2026, 11, 12, 18, 3, 0))        # the minute the import ran
stamp = time.strftime("%d/%m/%Y %H:%M", time.localtime(came))
old = store.set_location("Ega", "Ega 3", "1", lat=5.0, lon=5.0, radius_m=RADIUS)
old["notes"] = "Imported from another tool %s" % stamp
old["recorded"] = utc(came + 7)                         # stamped by the import, seconds later
find = store.add_deposit(system="Ega", body="Ega 3", location="1", commodity="Iridium", rigs="4",
                         lat="5.01", lon="5.0", notes="Imported from another tool %s" % stamp,
                         recorded="2026-11-10T19:40:00Z")
check("the import's own stamp on the signal is not a visit; the find's date is",
      last(store, "Ega 3", "1") == "2026-11-10T19:40:00Z", last(store, "Ega 3", "1"))
find["recorded"] = utc(came + 9)                        # a find the file gave no date for
check("a find stamped by the import is not one either", last(store, "Ega 3", "1") == "", last(store, "Ega 3", "1"))
check("nothing on disk was rewritten to work that out",
      old["recorded"] == utc(came + 7) and find["recorded"] == utc(came + 9))
old["recorded"] = utc(came + 3 * 86400)
check("a signal an import made, logged for real days later, is a visit",
      last(store, "Ega 3", "1") == utc(came + 3 * 86400), last(store, "Ega 3", "1"))

store = fresh("older")
store.add_deposit(system="Ega", body="Ega 4", location="1", commodity="Gold", lat="1", lon="1",
                  notes="imported from surfaceminingmap.csv (with signal centres)")
store.add_deposit(system="Ega", body="Ega 5", location="2", commodity="Gold", lat="1", lon="1",
                  notes="pasted from a shared line %s" % TODAY)
check("a find from the older file import carries no date of its own", last(store, "Ega 4", "1") == "",
      last(store, "Ega 4", "1"))
check("nor does a pasted line", last(store, "Ega 5", "2") == "", last(store, "Ega 5", "2"))
check("the helper says which rows came in", SV.came_in(store.deposits[0])[0] and SV.came_in(store.deposits[1])[0]
      and not SV.came_in({"notes": "my own note"})[0] and not SV.came_in({})[0])

print("== being there after an import ==")
store = fresh("worked")
store.set_location("Ega", "Ega 6", "1", lat=10.0, lon=20.0, radius_m=RADIUS, recorded="")
dep = store.add_deposit(system="Ega", body="Ega 6", location="1", commodity="Iridium", rigs="4",
                        lat="10.0", lon="20.0", notes="imported from surfaceminingmap.csv (with signal centres)")
check("before: no date", last(store, "Ega 6", "1") == "", last(store, "Ega 6", "1"))
check("the records have a column for the last tonne", "mined_at" in SV.DEPOSIT_FIELDS)
got = store.credit_refined("Ega", "Ega 6", 10.0, 20.0, RADIUS, "Iridium")
check("a tonne refined on a deposit dates it", got is dep and dep["mined_at"][:10] == TODAY, dep.get("mined_at"))
check("and that is when you were last there", (last(store, "Ega 6", "1") or "")[:10] == TODAY, last(store, "Ega 6", "1"))
dep["mined_at"] = ""
dep["depleted_at"] = "2026-11-05T10:00:00Z"
check("so is the day you found it worked out", last(store, "Ega 6", "1") == "2026-11-05T10:00:00Z")
dep["rechecks"] = "2026-11-07T10:00:00Z;2026-11-09T11:00:00Z"
check("and each look that found it still empty", last(store, "Ega 6", "1") == "2026-11-09T11:00:00Z",
      last(store, "Ega 6", "1"))
dep["cycles"] = "2026-11-11=300"
check("and each time it was worked out", (last(store, "Ega 6", "1") or "")[:10] == "2026-11-11", last(store, "Ega 6", "1"))
store.save_deposits()
again = SV.Survey(store.folder if hasattr(store, "folder") else os.path.dirname(store.deposits_path))
check("the new column survives a save and a load",
      [d.get("mined_at") for d in again.deposits] == [""] and "mined_at" in open(again.deposits_path, encoding="utf-8").readline())

print("== the pasted line and the older file import ==")
try:
    import _ctkstub  # noqa: F401
    import edsmt as A
    HAVE_APP = True
except Exception as problem:        # noqa: BLE001 - said, not hidden
    HAVE_APP = False
    print("  SKIP  the app could not be loaded here (%s)" % problem)
if HAVE_APP:
    store = fresh("paste")
    got = A.take_share_lines(store, "EDSMT find | Ega | Ega 7 | signal 2 | Gold | rigs 4 | amount High | density ? | 5, 2")
    check("a pasted find comes in", got["taken"] == 1 and got["signals"] == 1, got)
    check("its signal is not dated today", store.location("Ega", "Ega 7", "2")["recorded"] == "",
          store.location("Ega", "Ega 7", "2")["recorded"])
    check("and My sites has no date for it", last(store, "Ega 7", "2") == "", last(store, "Ega 7", "2"))

    folder = tempfile.mkdtemp(prefix="edsmt-lastthere-file-")
    A.DATA_DIR = folder
    path = os.path.join(folder, "surfaceminingmap.csv")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("system,planet,spotnum,type,rigs,lat,long,iscenter\n"
                     "Ega,Ega 8,3,,,2.0,2.0,true\n"
                     "Ega,Ega 8,3,Gold,4,2.01,2.0,false\n"
                     "Ega,Ega 9,1,Gold,4,3.0,3.0,false\n")
    store = fresh("file")
    got = A.import_finds(store, path)
    check("the older file import still works", got["ok"] and got["taken"] == 2 and got["signals"] == 2, got)
    check("its signals are not dated today",
          [r["recorded"] for r in store.locations] == ["", ""], [r["recorded"] for r in store.locations])
    check("and My sites has no date for them", [s["last"] for s in store.sites()] == ["", ""],
          [s["last"] for s in store.sites()])

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
