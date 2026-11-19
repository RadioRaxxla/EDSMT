"""1.10042: the import from another tool, finished.

What the other tool's database holds and the import used to leave behind:
tonnes per cycle, the depleted, regrown and recheck dates, the good and bad
marks, the centres, borders and swept ground of its maps. Also: the file is
found by itself and recognised by what is inside it; a bookmark with no
location number is not filed under signal 1; bookmarks the other tool had
itself taken from other people are kept for you, marked, and never sent;
bookmarks with no rigs are said; a database with a write-ahead file is read
whole; and bookmarks made since the last import are offered, not imported.

Every file here is built by the test, in the shape the layout notes give.

    python tests/test_110042_import.py
"""
import gzip
import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(HERE, "stubs"))
TMP = tempfile.mkdtemp(prefix="edsmt-import-")
os.environ["LOCALAPPDATA"] = TMP
os.environ["HOME"] = TMP

import survey as SV         # noqa: E402
import importers as IM      # noqa: E402
import importdb as IDB      # noqa: E402
import coverage as CV       # noqa: E402
import ownmarks as OM       # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


R = 1000000.0
HOME = (12.5, -45.5)


def dest(bearing, metres):
    lat0, lon0 = math.radians(HOME[0]), math.radians(HOME[1])
    d, b = metres / R, math.radians(bearing)
    lat = math.asin(math.sin(lat0) * math.cos(d) + math.cos(lat0) * math.sin(d) * math.cos(b))
    lon = lon0 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat0),
                            math.cos(d) - math.sin(lat0) * math.sin(lat))
    return math.degrees(lat), math.degrees(lon)


def record(commodity="Platinum", bearing=0, metres=800, **more):
    lat, lon = dest(bearing, metres)
    rec = {"system": "Ega", "planet_name": "Ega 1", "location_index": 2,
           "latitude": lat, "longitude": lon, "planet_radius": R,
           "commodity": commodity, "rigs": 4, "commander": "CMDR Own",
           "marked_at": "2026-10-02 09:30:00.123456+00:00", "system_address": 777}
    rec.update(more)
    return rec


def make(path, rows, marks=(), maps=(), wal=False, version=2):
    conn = sqlite3.connect(path)
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE bookmarks (id INTEGER PRIMARY KEY, system TEXT, "
                 "planet_name TEXT NOT NULL, system_address INTEGER, body_id INTEGER, "
                 "commodity TEXT, location_index INTEGER, rigs INTEGER, "
                 "depleted_at TEXT, data TEXT, source TEXT UNIQUE)")
    conn.execute("CREATE TABLE bodies (system TEXT, name TEXT, system_address INTEGER, "
                 "body_id INTEGER, data TEXT)")
    conn.execute("CREATE TABLE maps (body TEXT, name TEXT, system_address INTEGER, "
                 "body_id INTEGER, saved REAL, data BLOB)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("PRAGMA user_version=%d" % version)
    for rec in rows:
        conn.execute("INSERT INTO bookmarks (system, planet_name, system_address, commodity, "
                     "location_index, rigs, depleted_at, data) VALUES (?,?,?,?,?,?,?,?)",
                     (rec.get("system"), rec.get("planet_name"), rec.get("system_address"),
                      rec.get("commodity"), rec.get("location_index"), rec.get("rigs"),
                      rec.get("depleted_at"), json.dumps(rec)))
    for key, value in marks:
        conn.execute("INSERT INTO meta VALUES (?,?)", (key, str(value)))
    for body, name, data in maps:
        conn.execute("INSERT INTO maps VALUES (?,?,?,?,?,?)",
                     (body, name, data.get("system_address"), None, 1.0,
                      gzip.compress(json.dumps(data).encode())))
    conn.commit()
    return conn


def map_data(**more):
    c = dest(0, 0)
    data = {"version": 1, "body": "Ega 1", "saved": 5.0, "radius": R, "origin": list(c),
            "center": list(c), "border_m": 3000.0, "location": 2, "system_address": 777,
            "stamps": [list(dest(b, m)) for b, m in ((0, 100), (90, 500), (180, 900))]}
    data.update(more)
    return data


def fresh(name):
    return SV.Survey(tempfile.mkdtemp(prefix="edsmt-import-%s-" % name, dir=TMP))


def one(rows, **kw):
    path = os.path.join(tempfile.mkdtemp(dir=TMP), "x.db")
    make(path, rows, **kw).close()
    return path


def finds(path):
    return IM.read_path(path)


# ---------------------------------------------------------------------------
print("== F1: found by itself, recognised by what is inside ==")
base = tempfile.mkdtemp(dir=TMP)
home = os.path.join(base, "home")
data_root = os.path.join(home, ".local", "share")
dbdir = os.path.join(data_root, "SomeTool", "db")
os.makedirs(os.path.join(dbdir, "backups"))
live = os.path.join(dbdir, "tool.db")
make(live, [record(), record(commodity="Gold", bearing=90)]).close()
bak = os.path.join(dbdir, "backups", "copy-20261101.db")
shutil.copyfile(live, bak)
other = os.path.join(data_root, "Another", "notes.db")
os.makedirs(os.path.dirname(other))
c = sqlite3.connect(other)
c.execute("CREATE TABLE bookmarks (id INTEGER, url TEXT)")
c.commit()
c.close()
text = os.path.join(data_root, "Another", "readme.db")
with open(text, "w") as h:
    h.write("not a database at all")
found = IDB.locate(environ={}, home=home)
check("the database is found by looking, with no name given", [f["path"] for f in found][:1] == [live], found)
check("the live file comes before its backup", [f["backup"] for f in found] == [False, True], found)
check("it says how many bookmarks it holds", found and found[0]["bookmarks"] == 2, found)
check("a database of something else is not offered", other not in [f["path"] for f in found])
check("a file that is not a database is not offered", text not in [f["path"] for f in found])
renamed = os.path.join(base, "holiday-photos.dat")
shutil.copyfile(live, renamed)
check("a renamed copy is recognised by its contents", IDB.recognise(renamed) == (True, ""), IDB.recognise(renamed))
check("so is it in a folder of any name", IDB.recognise(bak)[0])
check("the other database is refused, with a reason", IDB.recognise(other)[0] is False and IDB.recognise(other)[1])
check("a file with the header but wrong rows is refused",
      IDB.recognise(one([{"system": "Ega", "planet_name": "Ega 1", "commodity": "Gold"}]))[0] is False)
os.remove(live)
alone = IDB.locate(environ={}, home=home)
check("with only a backup left, it is offered, as a backup", alone and alone[0]["backup"] and alone[0]["path"] == bak, alone)
os.makedirs(os.path.join(home, ".var", "app", "io.example.App", "data"))
check("the flatpak folder is searched when there",
      os.path.join(home, ".var", "app", "io.example.App", "data") in IDB.search_roots({}, home))

# ---------------------------------------------------------------------------
print("== F6 F7 F8: unplaced, other people's, no rigs ==")
rows = [record(bearing=0, metres=800),
        record(commodity="Gold", bearing=45, metres=900, location_index=0),
        record(commodity="Osmium", bearing=90, metres=900, location_index=None),
        record(commodity="Painite", bearing=120, metres=900, commander="@Import-Shared"),
        record(commodity="Monazite", bearing=150, metres=900, rigs=0),
        record(commodity="Bauxite", bearing=170, metres=900, rigs=0),
        record(commodity="Rutile", bearing=200, metres=900, rigs=None)]
path = one(rows)
source = finds(path)
store = fresh("f6")
plan = IM.make_plan(source, store)
by = {f["commodity"]: f for f in plan.new}
check("a bookmark with number 0 is not filed under signal 1", by["Gold"]["location"] == IM.NO_LOCATION, by["Gold"]["location"])
check("nor one with no number", by["Osmium"]["location"] == IM.NO_LOCATION)
check("the entry is named plainly", IM.NO_LOCATION == "no location recorded")
check("a bookmark with a number keeps it", by["Platinum"]["location"] == "2")
check("the preview counts them", any("2 with no location recorded" in l for l in plan.details()), plan.details())
check("the other people's one is flagged", by["Painite"]["not_mine"] and not by["Platinum"]["not_mine"])
check("the preview says so", any("1 came to the other tool from other people" in l for l in plan.details()), plan.details())
check("rigs of 0 are counted", by["Monazite"]["no_rigs"] and by["Bauxite"]["no_rigs"] and not by["Rutile"]["no_rigs"])
check("the preview says 2 with no rigs", any("2 with no rigs" in l for l in plan.details()), plan.details())
check("none of them is dropped silently", len(plan.new) == 7, len(plan.new))
result = IM.apply(plan, store, tempfile.mkdtemp(dir=TMP))
check("it imports", result["ok"] and result["taken"] == 7, result)
check("the unplaced ones sit under the named location",
      store.location("Ega", "Ega 1", IM.NO_LOCATION) is not None and
      sorted(d["commodity"] for d in store.at("Ega", "Ega 1", IM.NO_LOCATION)) == ["Gold", "Osmium"])
check("nothing is filed under signal 1", store.location("Ega", "Ega 1", "1") is None)
sent = [r["type"] for r in IM.community_rows(result["records"])]
check("the other people's find is never sent", "Painite" not in sent, sent)
check("a find with no location number is not sent either", "Gold" not in sent and "Osmium" not in sent, sent)
check("your own placed finds are sent", "Platinum" in sent and "Monazite" in sent, sent)
check("it is counted as kept for you", result["kept"] == 1, result.get("kept"))
mine = [d for d in store.deposits if d["commodity"] == "Painite"]
check("it is kept, marked as not yours", len(mine) == 1 and mine[0]["cmdr"] == IM.NOT_MINE
      and "not yours" in mine[0]["notes"].lower(), mine)
check("yours carry no other name", all(d["cmdr"] == "" for d in store.deposits if d["commodity"] == "Platinum"))

# ---------------------------------------------------------------------------
print("== F2 F3: tonnes, depleted, regrown, rechecks, last edited ==")
cycles = [
    {"from": "2026-09-20T10:00:00Z", "to": "2026-09-20T11:00:00Z", "tons": {"Platinum": 56, "Gold": 4},
     "rigs": 4, "density": "Medium", "amount_at_start": "High", "ended": "depleted", "ended_at": "2026-09-20T11:30:00Z"},
    {"from": "2026-10-01T10:00:00Z", "to": "2026-10-01T10:30:00Z", "tons": {"Platinum": 30},
     "amount_at_start": "Medium", "ended": "expired", "ended_at": "2026-10-03T10:30:00Z"},
    {"from": "2026-10-05T10:00:00Z", "to": "2026-10-05T12:00:00Z", "tons": {"Platinum": 48, "Gold": 2},
     "amount_at_start": "High", "ended": "depleted", "ended_at": "2026-10-05T12:10:00Z"},
    {"from": "2026-10-20T08:00:00Z", "to": "2026-10-20T08:45:00Z", "tons": {"Platinum": 21, "Copper": 3}},
]
rich = record(bearing=0, metres=800, updated_at="2026-11-01T18:00:00Z",
              regrown=[{"depleted_at": "2026-09-20T11:30:00Z", "regrown_at": "2026-10-01T10:00:00Z"},
                       {"depleted_at": "2026-10-05T12:10:00Z", "regrown_at": "2026-10-20T08:00:00Z"}],
              rechecks=["2026-10-10T09:00:00Z", "2026-10-12T09:00:00Z"],
              **{"yield": {"cycles": cycles}})
dep = record(commodity="Painite", bearing=90, metres=800, amount="Depleted",
             depleted_at="2026-10-18T08:00:00+00:00",
             regrown=[{"depleted_at": "2026-09-01T08:00:00Z", "regrown_at": "2026-09-20T08:00:00Z"}],
             **{"yield": {"cycles": [{"from": "2026-10-10T08:00:00Z", "to": "2026-10-10T09:00:00Z",
                                       "tons": {"Painite": 77}, "amount_at_start": "High",
                                       "ended": "depleted", "ended_at": "2026-10-18T08:00:00Z"}]}})
source = finds(one([rich, dep]))
store = fresh("f2")
plan = IM.make_plan(source, store)
f = {x["commodity"]: x for x in plan.new}
check("the open cycle's tonnes become what is mined here (by-products too)",
      SV.unpack_counts(f["Platinum"]["mined"]) == {"Platinum": 21, "Copper": 3}, f["Platinum"]["mined"])
check("each cycle worked out becomes a cycle, dated, its own commodity only",
      f["Platinum"]["cycles"] == "2026-09-20=56;2026-10-05=48", f["Platinum"]["cycles"])
check("a cycle that expired is not taken for a measure", "2026-10-03" not in f["Platinum"]["cycles"])
check("it is kept as a note instead", any("30 t" in t for _w, t in f["Platinum"]["notes_extra"]), f["Platinum"]["notes_extra"])
check("the last tonne's own date is kept, not the import's", f["Platinum"]["mined_at"] == "2026-10-20T08:45:00Z", f["Platinum"]["mined_at"])
check("rechecks come across", f["Platinum"]["rechecks"] == "2026-10-10T09:00:00Z;2026-10-12T09:00:00Z", f["Platinum"]["rechecks"])
check("a bookmark the other tool lifted keeps the first date it was depleted",
      f["Platinum"]["depleted_at"] == "2026-09-20T11:30:00Z", f["Platinum"]["depleted_at"])
check("and is not marked depleted now", f["Platinum"]["amount"] != "Depleted")
check("each regrowth is a note line, with its dates",
      sum("grown back" in t.lower() for _w, t in f["Platinum"]["notes_extra"]) == 2, f["Platinum"]["notes_extra"])
check("a bookmark depleted now keeps its own date", f["Painite"]["depleted_at"] == "2026-10-18T08:00:00Z"
      and f["Painite"]["amount"] == "Depleted", (f["Painite"]["depleted_at"], f["Painite"]["amount"]))
check("the last-edited date is read", any("last edited" in t.lower() for _w, t in f["Platinum"]["notes_extra"]))
lines = plan.details()
check("the preview counts cycles and says only High ones measure what it holds",
      any("3 cycle(s) worked out" in l and "opened at High" in l for l in lines), lines)
check("the preview counts regrown and rechecks",
      any("3 taken off depleted" in l for l in lines) and any("2 recheck" in l for l in lines), lines)
result = IM.apply(plan, store, tempfile.mkdtemp(dir=TMP))
row = [d for d in store.deposits if d["commodity"] == "Platinum"][0]
check("the deposit is stored with them", row["cycles"] == "2026-09-20=56;2026-10-05=48"
      and SV.unpack_counts(row["mined"])["Platinum"] == 21 and row["rechecks"].count(";") == 1, row)
check("its notes still begin with the import line", row["notes"].lower().startswith("imported from "), row["notes"])
check("and carry the regrown and last-edited lines",
      "grown back" in row["notes"].lower() and "last edited" in row["notes"].lower(), row["notes"])
check("tonnes known: the estimate sees the cycles", SV.cycle_tonnes(row) == [56, 48], SV.cycle_tonnes(row))
check("Last there comes from the record, not the day of the import",
      SV.last_there(row)[:10] == "2026-10-20", SV.last_there(row))

# ---------------------------------------------------------------------------
print("== F4: marks, kept on this PC ==")
marks = [("spot:Ega|Ega 1|2", 1), ("spot:Ega|Ega 1|3", -1), ("spot:Ega|Ega 1|0", 1),
         ("spot:Ega|Ega 1|5", 7), ("shared:abc", "2026"), ("lookup:777", "x")]
path = one([record()], marks=marks)
source = finds(path)
check("good and bad marks are read, nothing else in meta",
      sorted((m["location"], m["mark"]) for m in source.marks) == [("2", "up"), ("3", "down")], source.marks)
store, book = fresh("f4"), OM.OwnMarks(os.path.join(TMP, "marks.json"))
book.set("Ega", "Ega 1", "3", "up")
plan = IM.make_plan(source, store, marks=book)
check("a mark you already have is not counted as new", [m["location"] for m in plan.marks] == ["2"], plan.marks)
check("the preview says kept on this PC", any("1 good and 0 bad" in l and "never shared" in l for l in plan.details()), plan.details())
result = IM.apply(plan, store, tempfile.mkdtemp(dir=TMP), marks=book)
check("the mark is in the own-marks store", book.mine("Ega", "Ega 1", "2") == OM.UP, book.marks)
check("your own mark on the other location is not overwritten", book.mine("Ega", "Ega 1", "3") == OM.UP)
book.save()
reread = OM.OwnMarks(book.path)
reread.load()
check("and read back", reread.mine("Ega", "Ega 1", "2") == OM.UP)
check("marks go nowhere else: the community rows carry none",
      all("mark" not in r for r in IM.community_rows(result["records"])))
only = IM.make_plan(IM.read_path(one([], marks=marks[:1])), fresh("f4b"), marks=OM.OwnMarks())
check("marks alone are enough to import", only.has_work, only.counts)

# ---------------------------------------------------------------------------
print("== F5: centres, borders and swept ground ==")
rows = [record(bearing=0, metres=800)]
maps = [("Ega 1", "map 1", map_data()),
        ("Ega 1", "map 2", map_data(center=None, location=None, system_address=777,
                                    origin=list(dest(90, 80000)),
                                    stamps=[list(dest(90, 80000)), list(dest(90, 80300))])),
        ("Nowhere 9", "map 1", map_data(system_address=99999, body="Nowhere 9")),
        ("Ega 1", "map 3", {"version": 1, "stamps": []})]
path = one(rows, maps=maps)
source = finds(path)
check("maps are read, one with nothing on it is not, one with no system is counted",
      len(source.maps) == 2 and source.skipped_maps == 1 and source.skipped.get(IM.SKIP_MAP_SYSTEM) == 1,
      (len(source.maps), source.skipped_maps, source.skipped))
first = [m for m in source.maps if m["name"] == "map 1" and m["body"] == "Ega 1"][0]
check("the system is found from its address", first["system"] == "Ega", first["system"])
check("a map is placed on the signal it names", first["location"] == "2")
book = CV.CoverageBook(tempfile.mkdtemp(dir=TMP))
store = fresh("f5")
plan = IM.make_plan(source, store, coverage=book)
check("a map whose system cannot be found is said, not guessed",
      any("system not found" in k for k in plan.skipped), plan.skipped)
check("the preview counts maps, centres, borders and painted points",
      any("2 map(s)" in l and "1 centre" in l and "1 border" in l and "5 painted" in l for l in plan.details()), plan.details())
result = IM.apply(plan, store, tempfile.mkdtemp(dir=TMP), coverage=book)
check("maps are saved", result["maps"] == 2, result)
got = CV.CoverageBook(book.folder.rsplit(os.sep, 1)[0]).maps_on("Ega", "Ega 1")
check("they reload from disk", len(got) == 2, len(got))
cm = [m for m in got if m.centre is not None][0]
check("the centre, border and ground driven are as surveyed",
      abs(cm.centre[0] - HOME[0]) < 1e-6 and cm.border_m == 3000.0 and len(cm.points) == 3
      and cm.signal == "2" and cm.radius_m == R, (cm.centre, cm.border_m, len(cm.points), cm.signal))
check("swept ground answers", cm.swept_at(*dest(0, 100)))
loc = store.location("Ega", "Ega 1", "2")
check("the location opens with the centre as surveyed",
      loc is not None and abs(float(loc["lat"]) - HOME[0]) < 1e-5, loc)
again = IM.make_plan(source, store, coverage=book)
check("a second import finds the maps already held", len(again.maps) == 0 and again.maps_held == 2, (len(again.maps), again.maps_held))
mine_store = fresh("f5c")
mine_store.set_location("Ega", "Ega 1", "2", lat=1.0, lon=2.0, radius_m=R)
IM.apply(IM.make_plan(source, mine_store, coverage=CV.CoverageBook(tempfile.mkdtemp(dir=TMP))),
         mine_store, tempfile.mkdtemp(dir=TMP), coverage=CV.CoverageBook(tempfile.mkdtemp(dir=TMP)))
check("a centre you logged yourself is never moved",
      float(mine_store.location("Ega", "Ega 1", "2")["lat"]) == 1.0)
lying = finds(one([record(bearing=0, metres=800)],
                  maps=[("Ega 1", "map 1", map_data(center=None, location=None,
                                                    stamps=[list(dest(0, 700)), list(dest(0, 900))]))]))
check("a map with no location takes it from the bookmarks lying on it",
      [m["location"] for m in lying.maps] == ["2"], [m["location"] for m in lying.maps])

# ---------------------------------------------------------------------------
print("== F9: map pictures are an option, off by default ==")
pics = tempfile.mkdtemp(dir=TMP)
tool = os.path.join(tempfile.mkdtemp(dir=TMP), "RootFolder")
os.makedirs(os.path.join(tool, "db"))
os.makedirs(os.path.join(tool, "coverage", "Ega 1"))
with open(os.path.join(tool, "coverage", "Ega 1", "map 1.png"), "wb") as h:
    h.write(b"\x89PNG-test")
dbp = os.path.join(tool, "db", "t.db")
make(dbp, [record()]).close()
source = finds(dbp)
check("the pictures beside the database are listed", len(source.pictures) == 1, source.pictures)
plan = IM.make_plan(source, fresh("f9"))
IM.apply(plan, fresh("f9a"), tempfile.mkdtemp(dir=TMP), pictures_folder=pics)
check("by default none are copied", os.listdir(pics) == [], os.listdir(pics))
store = fresh("f9b")
result = IM.apply(IM.make_plan(source, store), store, tempfile.mkdtemp(dir=TMP),
                  pictures_folder=pics, copy_pictures=True)
check("when asked they are copied", result["pictures"] == 1 and len(os.listdir(pics)) == 1, (result, os.listdir(pics)))

# ---------------------------------------------------------------------------
print("== F10: a database with a write-ahead file is read whole ==")
wal = os.path.join(tempfile.mkdtemp(dir=TMP), "w.db")
conn = make(wal, [record()], wal=True)
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
for n in range(3):
    rec = record(commodity="Gold", bearing=10 * n, metres=1000 + n)
    conn.execute("INSERT INTO bookmarks (system, planet_name, commodity, location_index, rigs, data) "
                 "VALUES (?,?,?,?,?,?)", ("Ega", "Ega 1", "Gold", 2, 4, json.dumps(rec)))
conn.commit()
check("the new rows are in the write-ahead file, not the main one",
      os.path.getsize(wal + "-wal") > 0)
im = sqlite3.connect(IDB.Path(wal).as_uri() + "?immutable=1", uri=True)
seen = im.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
im.close()
check("an immutable read misses them (why the old fallback was wrong)", seen == 1, seen)
check("the ordinary read-only open sees all four", len(IDB.read(wal).rows) == 4, len(IDB.read(wal).rows))
fallback = IDB.read(wal, force_fallback=True)
check("the fallback sees all four too", len(fallback.rows) == 4 and not fallback.error, (len(fallback.rows), fallback.error))
check("it leaves the original and its write-ahead file alone",
      os.path.exists(wal + "-wal") and os.path.getsize(wal + "-wal") > 0)
check("and no copy is left behind", not [n for n in os.listdir(tempfile.gettempdir()) if n.startswith("edsmt-readcopy-")])
check("recognising works by the fallback as well", IDB.recognise(wal, force_fallback=True)[0])
conn.close()

# ---------------------------------------------------------------------------
print("== F11: bookmarks made since the last import are offered, never imported ==")
db = os.path.join(tempfile.mkdtemp(dir=TMP), "n.db")
conn = make(db, [record(bearing=b, metres=800 + b) for b in range(0, 40, 10)])
conn.commit()
state = os.path.join(tempfile.mkdtemp(dir=TMP), "import_state.json")
check("before any import nothing is offered as new since", IM.new_since(state, db) is None)
store = fresh("f11")
source = finds(db)
result = IM.apply(IM.make_plan(source, store), store, tempfile.mkdtemp(dir=TMP), state_path=state)
check("the import is remembered", os.path.exists(state) and result["taken"] == 4, result)
check("straight after, nothing is new", IM.new_since(state, db) == 0, IM.new_since(state, db))
for n in range(12):
    rec = record(commodity="Gold", bearing=60 + n, metres=2000 + 10 * n)
    conn.execute("INSERT INTO bookmarks (system, planet_name, commodity, location_index, rigs, data) "
                 "VALUES (?,?,?,?,?,?)", ("Ega", "Ega 1", "Gold", 2, 4, json.dumps(rec)))
conn.commit()
conn.close()
check("twelve more in the other tool are noticed", IM.new_since(state, db) == 12, IM.new_since(state, db))
offer = IM.offer(state, found=[{"path": db}])
check("they are offered in words", offer and offer["new"] == 12 and "12 new since your last import" in offer["text"], offer)
check("and noticing changes nothing", len(store.deposits) == 4)
check("nothing is offered when the database cannot be read", IM.new_since(state, os.path.join(TMP, "gone.db")) is None)

# ---------------------------------------------------------------------------
print("== the older checks still stand ==")
plan = IM.make_plan(finds(one([record(), record(commodity="Gold", rigs=13)])), fresh("old"))
check("rigs past what a site takes are still blank", [f["rigs"] for f in plan.new] == ["4", ""], [f["rigs"] for f in plan.new])
check("a plan with nothing in it has no work", not IM.make_plan(IM.read_path(one([])), fresh("e")).has_work
      if not IM.read_path(one([])).error else True)
check("the name of another tool is nowhere in the new module",
      ("rhino" + "spotter") not in open(os.path.join(REPO, "importdb.py"), encoding="utf-8").read().lower())

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
