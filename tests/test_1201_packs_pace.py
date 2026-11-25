"""1.201: recordings fetched one at a time are fetched a few at a time.

The first fetch is several hundred recordings. Asked for one after another
in one go it took more than the community map gives one PC, most of it was
refused, and the map's other calls - the wing link, the leaderboard, prices -
waited behind it. A pack now comes whole (test_1201_packs_whole.py); what is
still fetched file by file - a handful of new recordings, or a pack the map
does not offer whole - goes a few at a time with a pause between, stops at
once when the map says it is busy, and carries on from where it stopped, in
this run or the next.

    python tests/test_1201_packs_pace.py
"""
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-packs-pace-")

import packs as PX      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


class Marked:
    """Stands in for Windows' own protection."""

    def protect(self, data):
        return b"PC:" + bytes(data)

    def unprotect(self, data):
        if not bytes(data).startswith(b"PC:"):
            raise ValueError("not this PC's")
        return bytes(data)[3:]


def pack_of(count):
    files = {"line_%03d.wav" % n: (b"RIFF" + bytes([n % 251]) * 40) for n in range(count)}
    listing = {"packs": [{"pack": "celestia", "files": [
        {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in sorted(files.items())]}]}
    return files, listing


def kept(root):
    return sorted(f for _d, _s, fs in os.walk(os.path.join(root, "voice")) for f in fs)


print("== the pace ==")
check("a few at a time", 1 <= PX.SLICE <= 15, PX.SLICE)
check("with a pause between", PX.SLICE_GAP_S >= 5, PX.SLICE_GAP_S)
check("so no more than about one a second, however long the list",
      PX.SLICE / float(PX.SLICE_GAP_S) <= 1.5, PX.SLICE / float(PX.SLICE_GAP_S))
check("a longer wait when the map says it is busy", PX.BUSY_GAP_S >= 60 > PX.SLICE_GAP_S, PX.BUSY_GAP_S)
check("and longer again when the list cannot be had at all", PX.RETRY_S >= 300, PX.RETRY_S)

print("== a few at a time, carried on where it stopped ==")
files, listing = pack_of(12)
asked = []


def fetch(pack, name):
    asked.append(name)
    return files[name]


root = os.path.join(TMP, "slices")
vault = PX.Vault(root, Marked())
done = PX.sync(listing, fetch, root, vault, most=5)
check("the first call fetches five, and says seven are left",
      done["got"] == 5 and done["left"] == 7 and len(asked) == 5 and not done["stopped"], done)
done = PX.sync(listing, fetch, root, vault, most=5)
check("the next carries on: five more, none fetched twice",
      done["got"] == 5 and done["kept"] == 5 and done["left"] == 2 and len(set(asked)) == 10, (done, asked))
done = PX.sync(listing, fetch, root, vault, most=5)
check("and the last two", done["got"] == 2 and done["left"] == 0 and len(kept(root)) == 12, done)
done = PX.sync(listing, fetch, root, vault, most=5)
check("then there is nothing to do", done["got"] == 0 and done["kept"] == 12 and done["left"] == 0
      and len(asked) == 12, (done, len(asked)))
check("with no limit given, the whole list as before",
      PX.sync(listing, fetch, os.path.join(TMP, "whole"), PX.Vault(os.path.join(TMP, "whole"), Marked()))["got"] == 12)

print("== the map says it is busy: stop at once ==")
asked.clear()


def busy_fetch(pack, name):
    asked.append(name)
    if len(asked) >= 3:
        raise RuntimeError("the map is having trouble at its end (HTTP 503).")
    return files[name]


root = os.path.join(TMP, "busy")
vault = PX.Vault(root, Marked())
done = PX.sync(listing, busy_fetch, root, vault, most=10)
check("the two that arrived are kept", done["got"] == 2 and len(kept(root)) == 2, done)
check("it stopped at the refusal: not one more asked for", len(asked) == 3 and done["stopped"] is True, asked)
check("and the rest are left for later, not counted as failed", done["left"] == 10 and done["failed"] == 0, done)
asked.clear()
done = PX.sync(listing, fetch, root, vault, most=10)
check("later it carries on from there", done["got"] == 10 and done["kept"] == 2 and done["left"] == 0, done)

print("== a recording that arrives wrong is passed over, not asked for over and over ==")
asked.clear()
wrong = dict(files)
wrong["line_001.wav"] = b"not what the list says"


def wrong_fetch(pack, name):
    asked.append(name)
    return wrong[name]


root = os.path.join(TMP, "wrong")
vault = PX.Vault(root, Marked())
done = PX.sync(listing, wrong_fetch, root, vault, most=4)
check("it is not kept, and is named", done["failed"] == 1 and done["bad"] == ["celestia/line_001.wav"]
      and "line_001.wav.rrv" not in kept(root), done)
check("it counted towards this call's few", len(asked) == 4 and done["got"] == 3, (asked, done))
before = len(asked)
done = PX.sync(listing, wrong_fetch, root, vault, most=20, skip=done["bad"])
check("named again, it is not fetched again in this run", "line_001.wav" not in asked[before:], asked[before:])
check("and does not keep the run from ending", done["left"] == 0 and done["got"] == 8, done)

print("== the worker's job: the list asked for once in a run ==")
files, listing = pack_of(7)
lists, gets = [], []


def get_json(url, timeout=0, headers=None):
    lists.append((url, headers))
    return listing


def get_bytes(url, timeout=0, headers=None):
    gets.append((url, headers))
    return files[url.rsplit("/", 1)[1]]


root = os.path.join(TMP, "job")
vault = PX.Vault(root, Marked())
run = {}
HEAD = {"Authorization": "Bearer grant"}
first = json.loads(PX.sync_job("https://map.example", HEAD, get_json, get_bytes, root, vault, most=3, state=run)())
second = json.loads(PX.sync_job("https://map.example", HEAD, get_json, get_bytes, root, vault, most=3, state=run)())
third = json.loads(PX.sync_job("https://map.example", HEAD, get_json, get_bytes, root, vault, most=3, state=run)())
check("three, three and one", (first["got"], second["got"], third["got"]) == (3, 3, 1)
      and (first["left"], second["left"], third["left"]) == (4, 1, 0), (first, second, third))
check("the list was asked for once, with the header", lists == [("https://map.example/v1/packs", HEAD)], lists)
check("every file with the header too", len(gets) == 7 and all(h == HEAD for _u, h in gets))
check("the run over, the next one asks for the list afresh", "listing" not in run, list(run))
json.loads(PX.sync_job("https://map.example", HEAD, get_json, get_bytes, root, vault, most=3, state=run)())
check("as it does", len(lists) == 2 and len(gets) == 7, (len(lists), len(gets)))

print("== the app: one small job, a pause, the next ==")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
try:
    import edsmt as A
except Exception as exc:          # no Tk here: the checks above still count
    A = None
    print("  SKIP  the app's wiring needs Tk (%s)" % exc)

if A is not None:
    import perks as PK

    class Worker:
        def __init__(self):
            self.jobs = []

        def submit(self, tag, fn):
            self.jobs.append((tag, fn))

    A.DATA_DIR = os.path.join(TMP, "appdata-data")

    def new_app():
        app = A.EDSMT.__new__(A.EDSMT)
        app.settings = {"community_token": "staff-key"}
        app.perks_active = lambda role: False
        app.perks_state = lambda: {"supporter": False, "grant": ""}
        app.worker = Worker()
        app.pack_worker = Worker()     # 1.201: the packs have a worker of their own
        app.community = type("C", (), {"base_url": "https://map.example"})()
        app.clock = [1000.0]
        app.perks_clock = lambda: app.clock[0]
        app.said = []
        app.say = lambda text, colour=None: app.said.append(text)
        return app

    def answer(**done):
        base = {"got": 0, "kept": 0, "failed": 0, "removed": 0, "left": 0, "stopped": False}
        base.update(done)
        return json.dumps(base)

    app = new_app()
    check("the first look asks", app.follow_packs(1000.0) is True and len(app.pack_worker.jobs) == 1
          and app.pack_worker.jobs[0][0] == PX.JOB_TAG, app.pack_worker.jobs)
    check("not a second job while that one is out", app.follow_packs(1001.0) is False and len(app.pack_worker.jobs) == 1)
    app.clock[0] = 1003.0
    app.take_packs(True, answer(got=PX.SLICE, left=500))
    check("more to come: it says so once, in plain words",
          len(app.said) == 1 and "Supporter voices" in app.said[0] and "500 more" in app.said[0], app.said)
    check("with about how long, worked out from what is left",
          "about %d minutes" % PX.minutes_for(500) in app.said[0] and 5 <= PX.minutes_for(500) <= 20
          and PX.minutes_for(3) == 1 and PX.minutes_for(None) == 1, (app.said, PX.minutes_for(500)))
    check("the next few wait for the pause", app.follow_packs(1003.0 + PX.SLICE_GAP_S - 1) is False)
    check("then go", app.follow_packs(1003.0 + PX.SLICE_GAP_S) is True and len(app.pack_worker.jobs) == 2)
    app.clock[0] = 1020.0
    app.take_packs(True, answer(got=2, left=498, stopped=True))
    check("the map busy: the longer wait", app.follow_packs(1020.0 + PX.SLICE_GAP_S + 1) is False
          and app.follow_packs(1020.0 + PX.BUSY_GAP_S) is True, app.pack_worker.jobs)
    check("and nothing more said meanwhile", len(app.said) == 1, app.said)
    app.clock[0] = 1200.0
    app.take_packs(False, "no connection")
    check("the list not had: it waits, and neither gives up for six hours nor asks at once",
          app.follow_packs(1201.0) is False and app.follow_packs(1200.0 + PX.RETRY_S) is True)
    app.clock[0] = 2000.0
    app.take_packs(True, answer(got=3, kept=527, left=0))
    check("all here: said once, with how many came in the whole run",
          len(app.said) == 2 and str(PX.SLICE + 2 + 3) in app.said[1] and "ready" in app.said[1], app.said)
    check("then about every six hours, as before", app.follow_packs(2000.0 + PX.SLICE_GAP_S) is False
          and app.follow_packs(2000.0 + PK.EVERY_S) is True)
    app.clock[0] = 2000.0 + PK.EVERY_S + 5
    app.take_packs(True, answer(kept=530, left=0))
    check("a look that finds nothing new says nothing", len(app.said) == 2, app.said)

    app = new_app()
    app.follow_packs(1000.0)
    app.take_packs(True, answer(got=4, left=0))
    check("a short list arrives in one go and is said once, as ready",
          len(app.said) == 1 and "4 new recordings ready" in app.said[0], app.said)

    app = new_app()
    app.follow_packs(1000.0)
    app.take_packs(True, answer(got=9, failed=1, left=0))
    check("one that did not arrive whole is owned up to", len(app.said) == 1 and "9 new" in app.said[0]
          and "1 " in app.said[0].split("ready", 1)[1], app.said)

    app = new_app()
    app.settings["community_token"] = ""
    check("a free install asks for nothing", app.follow_packs(1000.0) is False and not app.pack_worker.jobs)

    app = new_app()
    seen = {}
    real = PX.sync_job

    def spy(base_url, header, get_json, get_bytes, root, vault, most=0, state=None):
        seen.update(most=most, state=state, base_url=base_url)
        return lambda: answer()

    PX.sync_job = spy
    try:
        app.follow_packs(1000.0)
    finally:
        PX.sync_job = real
    check("each job is told to fetch only a few, and shares the run's notes",
          seen.get("most") == PX.SLICE and isinstance(seen.get("state"), dict), seen)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
