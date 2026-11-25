"""1.201: supporter voices come whole.

A pack is several hundred recordings. Fetched a few at a time they took ten
minutes to arrive, and meanwhile most of the voice was missing. Now the map
offers the pack as one file: EDSMT fetches it in one go, checks it and every
recording in it against the SHA-256 the list gives, and keeps each sealed -
so the whole voice is there together. One at a time is kept for a handful of
new recordings, and for when the one file cannot be had.

The fetch runs on a thread of its own, so nothing else EDSMT asks the map
waits behind it.

    python tests/test_1201_packs_whole.py
"""
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-packs-whole-")

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


def zip_of(members):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as made:
        for name, data in members.items():
            made.writestr(name, data)
    return out.getvalue()


def pack_of(count, whole=True, extra=None):
    """(files, the map's list, the pack's one file)."""
    files = {"line_%03d.wav" % n: (b"RIFF" + bytes([n % 251]) * (40 + n)) for n in range(count)}
    files["chatty/line_000-2.wav"] = b"RIFF" + b"q" * 33
    members = dict(files)
    members.update(extra or {})
    blob = zip_of(members)
    entry = {"pack": "celestia", "files": [
        {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in sorted(files.items())]}
    if whole:
        entry["archive"] = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
    return files, {"packs": [entry]}, blob


def kept(root):
    return sorted(os.path.relpath(os.path.join(d, f), os.path.join(root, "voice", "celestia")).replace(os.sep, "/")
                  for d, _s, fs in os.walk(os.path.join(root, "voice")) for f in fs)


def everything(root):
    return [os.path.join(d, f) for d, _s, fs in os.walk(root) for f in fs]


class Calls:
    """The two ways of fetching, with what was asked of each."""

    def __init__(self, files, blob):
        self.files, self.blob, self.one, self.whole = files, blob, [], []

    def fetch(self, pack, name):
        self.one.append(name)
        got = self.files[name]
        if isinstance(got, Exception):
            raise got
        return got

    def archive(self, pack):
        self.whole.append(pack)
        if isinstance(self.blob, Exception):
            raise self.blob
        return self.blob


def fresh(name):
    root = os.path.join(TMP, name)
    return root, PX.Vault(root, Marked())


MANY = PX.ARCHIVE_OVER + 20

print("== what the list offers whole ==")
files, listing, blob = pack_of(MANY)
check("the pack, with the size and SHA-256 of its one file",
      PX.archives(listing) == {"celestia": (len(blob), hashlib.sha256(blob).hexdigest())}, PX.archives(listing))
check("a list that offers none", PX.archives(pack_of(3, whole=False)[1]) == {} and PX.archives({}) == {}
      and PX.archives(None) == {})
odd = json.loads(json.dumps(listing))
odd["packs"][0]["archive"] = {"bytes": "lots", "sha256": "zz"}
check("an offer that is not a size and a SHA-256 is no offer", PX.archives(odd) == {})
check("more than a handful missing is what it is for", 5 <= PX.ARCHIVE_OVER <= 50, PX.ARCHIVE_OVER)

print("== the whole pack in one go ==")
root, vault = fresh("whole")
calls = Calls(files, blob)
done = PX.sync(listing, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("asked for once, as one file", calls.whole == ["celestia"], calls.whole)
check("and not one recording asked for by itself", calls.one == [], calls.one[:3])
check("every recording is here after the one call, whatever a few-at-a-time limit says",
      done["got"] == len(files) and done["left"] == 0 and len(kept(root)) == len(files), done)
check("in its sub-folder where it has one", "chatty/line_000-2.wav.rrv" in kept(root), kept(root)[:3])
check("each kept sealed, never as a plain wave",
      all(f.endswith(".rrv") or os.path.basename(f) in (PX.KEY_FILE, PX.MANIFEST) for f in everything(root))
      and not any(open(f, "rb").read(4) == b"RIFF" for f in everything(root)))
check("and opens as the recording it is",
      vault.read(os.path.join(root, "voice", "celestia", "line_007.wav.rrv")) == files["line_007.wav"])
check("it says the pack came whole", done.get("whole") == ["celestia"], done)
calls = Calls(files, blob)
done = PX.sync(listing, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("asked again with everything here, nothing is fetched at all",
      calls.whole == [] and calls.one == [] and done["kept"] == len(files) and done["got"] == 0, done)

print("== a handful missing: one at a time, not the whole pack again ==")
for name in ("line_003.wav", "line_004.wav"):
    os.remove(os.path.join(root, "voice", "celestia", name + ".rrv"))
calls = Calls(files, blob)
done = PX.sync(listing, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("the two are fetched by themselves", calls.whole == [] and sorted(calls.one) == ["line_003.wav", "line_004.wav"]
      and done["got"] == 2 and done["left"] == 0, (calls.whole, calls.one, done))

print("== a list that offers no whole file: one at a time, as before ==")
files2, listing2, blob2 = pack_of(MANY, whole=False)
root, vault = fresh("none")
calls = Calls(files2, blob2)
done = PX.sync(listing2, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("nothing whole is asked for, and the few-at-a-time limit holds",
      calls.whole == [] and len(calls.one) == 10 and done["got"] == 10 and done["left"] == len(files2) - 10, done)

print("== a whole file that is not the one the list described ==")
root, vault = fresh("wrong")
calls = Calls(files, blob[:-7] + b"tamper!")
done = PX.sync(listing, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("nothing in it is used", done.get("no_archive") == ["celestia"] and not done.get("whole"), done)
check("and the recordings come one at a time instead, in the same call",
      len(calls.one) == 10 and done["got"] == 10 and done["left"] == len(files) - 10, done)
calls2 = Calls(files, blob[:-7] + b"tamper!")
done = PX.sync(listing, calls2.fetch, root, vault, most=10, fetch_archive=calls2.archive, no_archive=done["no_archive"])
check("told so, the next call does not ask for the whole file again", calls2.whole == [] and done["got"] == 10, calls2.whole)

root, vault = fresh("notzip")
junk = b"this is not a zip file at all" * 40
bad_list = json.loads(json.dumps(listing))
bad_list["packs"][0]["archive"] = {"bytes": len(junk), "sha256": hashlib.sha256(junk).hexdigest()}
calls = Calls(files, junk)
done = PX.sync(bad_list, calls.fetch, root, vault, most=5, fetch_archive=calls.archive)
check("a file that is not a zip: not used, no crash, one at a time",
      done.get("no_archive") == ["celestia"] and done["got"] == 5, done)

print("== the whole file cannot be had ==")
root, vault = fresh("refused")
calls = Calls(files, RuntimeError("the map replied HTTP 404."))
done = PX.sync(listing, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("it is noted, and the recordings come one at a time", done.get("no_archive") == ["celestia"]
      and done["got"] == 10 and not done["stopped"], done)
root, vault = fresh("down")
down = {name: OSError("no connection") for name in files}
calls = Calls(down, OSError("no connection"))
done = PX.sync(listing, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("with the map out of reach it stops after one try at each, with nothing counted as failed",
      calls.whole == ["celestia"] and len(calls.one) == 1 and done["stopped"] and done["failed"] == 0
      and done["left"] == len(files), (calls.whole, len(calls.one), done))

print("== one recording in the whole file is wrong ==")
members = dict(files)
members["line_005.wav"] = b"RIFF" + b"not what the list says"
mixed = zip_of(members)
mixed_list = json.loads(json.dumps(listing))
mixed_list["packs"][0]["archive"] = {"bytes": len(mixed), "sha256": hashlib.sha256(mixed).hexdigest()}
root, vault = fresh("mixed")
calls = Calls(files, mixed)
done = PX.sync(mixed_list, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("the rest are kept from it", "line_006.wav.rrv" in kept(root) and done.get("whole") == ["celestia"], done)
check("and the wrong one is fetched by itself and kept right",
      calls.one == ["line_005.wav"] and done["left"] == 0
      and vault.read(os.path.join(root, "voice", "celestia", "line_005.wav.rrv")) == files["line_005.wav"],
      (calls.one, done))

print("== only what the list names is ever taken from it ==")
files3, listing3, blob3 = pack_of(MANY, extra={"../../outside.wav": b"RIFFescape", "not_listed.wav": b"RIFFextra",
                                              "/abs.wav": b"RIFFabs", "voice/celestia/../../up.wav": b"RIFFup"})
root, vault = fresh("extra")
calls = Calls(files3, blob3)
done = PX.sync(listing3, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("the listed recordings are kept", done["got"] == len(files3) and len(kept(root)) == len(files3), done)
check("and nothing else in the file is written anywhere",
      not any("outside" in f or "not_listed" in f or "abs.wav" in f or "up.wav" in f
              for f in everything(TMP)), [f for f in everything(TMP) if "outside" in f or "not_listed" in f])

print("== a recording far bigger than the list says is not unpacked ==")
bomb = dict(files)
bomb["line_002.wav"] = b"\0" * (PX.MEMBER_MAX + 1)
bomb_blob = zip_of(bomb)
bomb_list = json.loads(json.dumps(listing))
bomb_list["packs"][0]["archive"] = {"bytes": len(bomb_blob), "sha256": hashlib.sha256(bomb_blob).hexdigest()}
root, vault = fresh("bomb")
calls = Calls(files, bomb_blob)
done = PX.sync(bomb_list, calls.fetch, root, vault, most=10, fetch_archive=calls.archive)
check("it is passed over in the whole file and fetched by itself",
      calls.one == ["line_002.wav"] and done["left"] == 0 and done["got"] == len(files), (calls.one, done))
check("a whole file larger than EDSMT will take is not fetched into anything",
      PX.ARCHIVE_MAX >= 100 * 1024 * 1024 and PX.MEMBER_MAX >= 5 * 1024 * 1024)

print("== the worker's job ==")
files, listing, blob = pack_of(MANY)
lists, wholes, ones = [], [], []


def get_json(url, timeout=0, headers=None):
    lists.append((url, headers))
    return listing


def get_bytes(url, timeout=0, headers=None):
    (wholes if url.endswith(".zip") else ones).append((url, headers, timeout))
    return blob if url.endswith(".zip") else files[url.split("/v1/packs/celestia/", 1)[1]]


root, vault = fresh("job")
run = {}
HEAD = {"Authorization": "Bearer grant"}
done = json.loads(PX.sync_job("https://map.example", HEAD, get_json, get_bytes, root, vault, most=PX.SLICE, state=run)())
check("one list, one whole file, nothing else", len(lists) == 1 and len(wholes) == 1 and ones == [], (lists, wholes, ones))
check("the whole file is asked for by the pack's name, with the same header",
      wholes[0][0] == "https://map.example/v1/packs/celestia.zip" and wholes[0][1] == HEAD, wholes[0][:2])
check("and given longer than one recording is", wholes[0][2] == PX.ARCHIVE_TIMEOUT_S > PX.TIMEOUT_S, wholes[0][2])
check("everything is here after the one job", done["got"] == len(files) and done["left"] == 0, done)
check("the run's notes are cleared for the next run", run == {}, run)

print("== the app: a thread of its own, and one line when the voice is here ==")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
try:
    import edsmt as A
except Exception as exc:          # no Tk here: the checks above still count
    A = None
    print("  SKIP  the app's wiring needs Tk (%s)" % exc)

if A is not None:
    import edonline as EDO

    class Worker:
        def __init__(self):
            self.jobs = []

        def submit(self, tag, fn):
            self.jobs.append((tag, fn))

        def drain(self):
            out, self.jobs = [(tag, True, fn() or "") for tag, fn in self.jobs], []
            return out

    A.DATA_DIR = os.path.join(TMP, "appdata-data")
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = {"community_token": "staff-key"}
    app.perks_active = lambda role: False
    app.perks_state = lambda: {"supporter": False, "grant": ""}
    app.worker = Worker()
    app.pack_worker = Worker()
    app.community = type("C", (), {"base_url": "https://map.example"})()
    app.perks_clock = lambda: 1000.0
    app.said = []
    app.say = lambda text, colour=None: app.said.append(text)
    real_json, real_bytes = EDO.get_json, EDO.get_bytes
    EDO.get_json, EDO.get_bytes = get_json, get_bytes
    try:
        check("the fetch is started", app.follow_packs(1000.0) is True)
        check("on a worker of its own, so nothing else waits behind it",
              app.worker.jobs == [] and [t for t, _f in app.pack_worker.jobs] == [PX.JOB_TAG],
              (app.worker.jobs, app.pack_worker.jobs))
        for tag, ok, message in app.pack_worker.drain():
            app.take_packs(ok, message)
    finally:
        EDO.get_json, EDO.get_bytes = real_json, real_bytes
    check("one line, when the whole voice is here", len(app.said) == 1
          and "%d new recordings ready" % len(files) in app.said[0], app.said)
    check("and the next look is hours off, not seconds", app.follow_packs(1000.0 + PX.BUSY_GAP_S + PX.SLICE_GAP_S) is False)
    del app.pack_worker
    made = []
    real_worker = EDO.Worker
    EDO.Worker = lambda: made.append(Worker()) or made[-1]
    try:
        app._packs_due = 0
        app.follow_packs(99999999.0)
    finally:
        EDO.Worker = real_worker
    check("the worker is made the first time it is needed, and only once",
          len(made) == 1 and app.pack_worker is made[0], made)
    source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
    body = source.split("    def collect_results(self):", 1)[1].split("\n    def ", 1)[0]
    check("its results are collected with everybody else's", "pack_worker" in body, body[-400:])

print("== what the guide and the patch notes say ==")
guide = " ".join(open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read().split())
notes = " ".join(open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8").read().split("\n## 1.2\n")[0].split())
check("the guide says they come in one download", "one download" in guide, "")
check("and no longer over about ten minutes", "about ten minutes" not in guide)
check("the patch notes too", "one download" in notes and "a few at a time over the first minutes" not in notes)
security = " ".join(open(os.path.join(REPO, "SECURITY.md"), encoding="utf-8").read().split())
check("the security notes say a paired EDSMT asks the member page what it may have",
      "asks that page at start and every few hours what your membership gives it" in security)
check("that nothing about the game goes with the question", "nothing about your game goes with the question" in security)
check("and that the recordings are fetched from the community service", "fetches the extra recordings from the community service" in security)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
