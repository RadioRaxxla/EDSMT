"""Finding and reading another tool's database of bookmarks (1.10042).

Three jobs, none of them needing a window:

    locate()      look in the places such a database is kept and offer what is
                  there, newest first, each one recognised by what is inside it
    recognise()   say whether a file is one, by its header, its tables and
                  columns and a row - never by its name or the folder it is in
    read()        everything in it that is worth bringing in: the bookmarks
                  with their whole record, the marks on locations and the
                  surveyed maps

The file is only ever opened read-only. When another program has it open its
newest rows can still be in the write-ahead file beside it, and a read that
ignores that file misses them: open_read_only() copies the pair aside and
reads the copy rather than guess.

Written from the layout of the file as found on a PC; no code or data from the
other tool is used here, and its name is not written anywhere in this tree.
The places to look are found by looking, not by a list of names.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import zlib
from pathlib import Path

HEADER = b"SQLite format 3\x00"
KNOWN_VERSIONS = (1, 2)
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_MAP_BYTES = 32 * 1024 * 1024
MAX_POINTS = 200000
DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")
# The columns a bookmark table has to carry to be read at all, and the ones
# that make it look like the one this reads.
NEEDED = ("data", "planet_name")
EXPECTED = ("id", "system", "planet_name", "system_address", "body_id", "commodity",
            "location_index", "rigs", "depleted_at", "data")
MARK_PREFIX = "spot:"
MAX_FOLDERS = 400
MAX_CANDIDATES = 12


# ---------------------------------------------------------------------------
# Opening it without changing it
# ---------------------------------------------------------------------------

def _nothing():
    return None


def open_read_only(path, force_fallback=False):
    """(connection, cleanup) for reading a database without touching it.

    The ordinary read-only open sees the write-ahead file. When it is refused
    (a read-only folder, a lock) the fallback must not simply ignore that
    file, which hides every row not yet moved into the main one: the pair is
    copied to a temporary folder and the copy is read. With no write-ahead
    file there is nothing to miss and the file is read as it stands."""
    full = os.path.abspath(path)
    uri = Path(full).as_uri() + "?mode=ro"
    if not force_fallback:
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
            return conn, _nothing
        except sqlite3.Error:
            if conn is not None:
                conn.close()
    wal = full + "-wal"
    try:
        has_wal = os.path.getsize(wal) > 0
    except OSError:
        has_wal = False
    if not has_wal:
        return sqlite3.connect(uri.replace("mode=ro", "immutable=1"),
                               uri=True, timeout=5.0), _nothing
    spare = tempfile.mkdtemp(prefix="edsmt-readcopy-")

    def clean():
        shutil.rmtree(spare, ignore_errors=True)
    try:
        target = os.path.join(spare, "copy.db")
        shutil.copyfile(full, target)
        shutil.copyfile(wal, target + "-wal")
        return sqlite3.connect(target, timeout=5.0), clean
    except (OSError, sqlite3.Error):
        clean()
        raise


# ---------------------------------------------------------------------------
# Recognising it by what is inside
# ---------------------------------------------------------------------------

def _columns(conn, table):
    return [row[1] for row in conn.execute('PRAGMA table_info("%s")' % table)]


def _record(blob):
    try:
        found = json.loads(blob)
    except (TypeError, ValueError, RecursionError):
        return None
    return found if isinstance(found, dict) else None


def has_header(path):
    try:
        with open(path, "rb") as handle:
            return handle.read(16) == HEADER
    except OSError:
        return False


def recognise(path, force_fallback=False):
    """(ok, why): is this file a database of bookmarks, by its contents.

    The first 16 bytes, then a bookmarks table with the columns it needs, then
    a row whose record names a body and a position. The version number is
    noted, not insisted on: a newer file with the same tables is still read."""
    if not has_header(path):
        return False, "it is not a database file"
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return False, "it is too large"
    except OSError as problem:
        return False, str(problem)
    conn, clean = None, _nothing
    try:
        conn, clean = open_read_only(path, force_fallback)
        columns = _columns(conn, "bookmarks")
        if not columns or any(name not in columns for name in NEEDED):
            return False, "it has no bookmarks table this can read"
        rows = conn.execute("SELECT data FROM bookmarks LIMIT 5").fetchall()
        if rows and not any(
                (rec := _record(row[0])) and "planet_name" in rec
                and "latitude" in rec and "longitude" in rec for row in rows):
            return False, "its bookmarks are not in a shape this reads"
        return True, ""
    except (sqlite3.Error, OSError) as problem:
        return False, str(problem)
    finally:
        if conn is not None:
            conn.close()
        clean()


# ---------------------------------------------------------------------------
# Finding it
# ---------------------------------------------------------------------------

def search_roots(environ=None, home=None):
    """The folders whose sub-folders are looked into: where a program keeps
    its own data on Windows and on Linux, including a packaged app's."""
    env = os.environ if environ is None else environ
    home = home or os.path.expanduser("~")
    roots = []
    for value in (env.get("LOCALAPPDATA"), env.get("XDG_DATA_HOME"),
                  os.path.join(home, ".local", "share"),
                  os.path.join(home, "AppData", "Local"), home):
        if value and value not in roots:
            roots.append(value)
    flat = os.path.join(home, ".var", "app")
    try:
        for name in sorted(os.listdir(flat))[:50]:
            roots.append(os.path.join(flat, name, "data"))
    except OSError:
        pass
    return roots


def _databases_in(folder):
    """Files in a folder that carry the header, newest first."""
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for name in names:
        if not name.lower().endswith(DB_SUFFIXES):
            continue
        full = os.path.join(folder, name)
        try:
            if os.path.isfile(full) and has_header(full):
                out.append((os.path.getmtime(full), full))
        except OSError:
            continue
    return [path for _when, path in sorted(out, reverse=True)]


def locate(roots=None, environ=None, home=None):
    """The databases of bookmarks found, best first: [{path, backup, when,
    bookmarks}].

    Each sub-folder of each root is looked into, and its `db` folder and that
    folder's backups. Nothing is chosen by name: a file counts when
    recognise() says it is one. The live file comes before a backup, and a
    backup is offered when the live one is not there."""
    found, seen, looked = [], set(), 0
    for root in (roots if roots is not None else search_roots(environ, home)):
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            folder = os.path.join(root, name)
            if not os.path.isdir(folder):
                continue
            looked += 1
            if looked > MAX_FOLDERS:
                break
            for sub, backup in ((folder, False), (os.path.join(folder, "db"), False),
                                (os.path.join(folder, "db", "backups"), True)):
                for path in _databases_in(sub)[:3]:
                    real = os.path.realpath(path)
                    if real in seen:
                        continue
                    seen.add(real)
                    ok, _why = recognise(path)
                    if ok:
                        found.append({"path": path, "backup": backup,
                                      "when": os.path.getmtime(path),
                                      "bookmarks": count_bookmarks(path)})
    found.sort(key=lambda item: (item["backup"], -item["when"]))
    return found[:MAX_CANDIDATES]


def count_bookmarks(path):
    """How many bookmarks a database holds, or 0."""
    conn, clean = None, _nothing
    try:
        conn, clean = open_read_only(path)
        return int(conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0])
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return 0
    finally:
        if conn is not None:
            conn.close()
        clean()


def bookmark_ids(path):
    """The ids of every bookmark in a database, or None when it cannot be read."""
    conn, clean = None, _nothing
    try:
        conn, clean = open_read_only(path)
        return {int(row[0]) for row in conn.execute("SELECT id FROM bookmarks")
                if row[0] is not None}
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return None
    finally:
        if conn is not None:
            conn.close()
        clean()


# ---------------------------------------------------------------------------
# Reading it
# ---------------------------------------------------------------------------

class Dump:
    """Everything read from one database, undecided."""

    def __init__(self):
        self.error = ""
        self.rows = []           # {"id", "cols", "record"}
        self.marks = []          # {"system", "body", "location", "mark"}
        self.maps = []           # see _map_entry()
        self.address_system = {}  # system address -> system name
        self.version = None
        self.skipped_maps = 0
        self.pictures = []       # (body, name, path) of saved map pictures


def _inflate(blob):
    """A map's record: gzip of JSON, or plain JSON. A dict, or None."""
    if isinstance(blob, str):
        blob = blob.encode("utf-8")
    if not isinstance(blob, (bytes, bytearray)):
        return None
    try:
        if bytes(blob[:2]) == b"\x1f\x8b":
            inflater = zlib.decompressobj(31)
            blob = inflater.decompress(bytes(blob), MAX_MAP_BYTES + 1)
            if len(blob) > MAX_MAP_BYTES:
                return None
        return _record(bytes(blob).decode("utf-8", "replace"))
    except (zlib.error, ValueError):
        return None


def _pair(value):
    try:
        lat, lon = float(value[0]), float(value[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0) or lat != lat or lon != lon:
        return None
    return lat, lon


def _positive(value):
    try:
        found = float(value)
    except (TypeError, ValueError):
        return None
    return found if found > 0 and found == found and found != float("inf") else None


def _map_entry(row, system_of):
    """One saved map as plain facts, or None when it has nothing on it."""
    body, name, address, _body_id, saved, blob = row
    data = _inflate(blob)
    if data is None:
        return None
    address = address if address not in (None, "") else data.get("system_address")
    stamps = data.get("stamps")
    points = []
    if isinstance(stamps, list):
        for item in stamps[:MAX_POINTS]:
            pair = _pair(item)
            if pair is not None:
                points.append(pair)
    centre = _pair(data.get("center"))
    if not points and centre is None:
        return None
    location = data.get("location")
    try:
        location = str(int(location)) if location not in (None, "", 0, "0") else ""
    except (TypeError, ValueError):
        location = ""
    return {"body": str(body or data.get("body") or "").strip(), "name": str(name or ""),
            "system": system_of(address, body), "address": address,
            "location": location, "centre": centre,
            "border_m": _positive(data.get("border_m")) if centre else None,
            "radius_m": _positive(data.get("radius")), "points": points,
            "saved": data.get("saved") or saved}


def _marks_from(meta_rows):
    out = []
    for key, value in meta_rows:
        key = str(key or "")
        if not key.startswith(MARK_PREFIX):
            continue
        try:
            mark = {1: "up", -1: "down"}.get(int(str(value).strip()))
        except ValueError:
            mark = None
        parts = key[len(MARK_PREFIX):].split("|")
        if mark is None or len(parts) < 3:
            continue
        number = parts[-1].strip()
        if not number.isdigit() or int(number) < 1:
            continue
        out.append({"system": parts[0].strip(), "body": "|".join(parts[1:-1]).strip(),
                    "location": str(int(number)), "mark": mark})
    return out


def _table_rows(conn, table, columns):
    """Rows of a table that may not be there: [] then."""
    have = _columns(conn, table)
    if not have:
        return []
    wanted = [c for c in columns if c in have]
    if len(wanted) != len(columns):
        return []
    try:
        return conn.execute("SELECT %s FROM \"%s\"" % (", ".join(columns), table)).fetchall()
    except sqlite3.Error:
        return []


def pictures_beside(path):
    """The map pictures the other tool saved beside its database, if any:
    [(body folder name, picture name, path)]. Looked for up to three folders
    above the file."""
    folder = os.path.dirname(os.path.abspath(path))
    for _step in range(3):
        base = os.path.join(folder, "coverage")
        if os.path.isdir(base):
            out = []
            try:
                for body in sorted(os.listdir(base)):
                    inner = os.path.join(base, body)
                    if not os.path.isdir(inner):
                        continue
                    for name in sorted(os.listdir(inner)):
                        if name.lower().endswith(".png"):
                            out.append((body, name, os.path.join(inner, name)))
            except OSError:
                return out
            return out
        folder = os.path.dirname(folder)
    return []


def read(path, force_fallback=False):
    """A Dump of the database at `path`; its .error says what went wrong."""
    dump = Dump()
    conn, clean = None, _nothing
    try:
        conn, clean = open_read_only(path, force_fallback)
        columns = _columns(conn, "bookmarks")
        if not columns or "data" not in columns:
            dump.error = "That database has no bookmarks table this can read."
            return dump
        try:
            dump.version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        except (sqlite3.Error, TypeError, ValueError):
            dump.version = None
        wanted = [c for c in ("id", "system", "planet_name", "system_address",
                              "commodity", "location_index", "rigs", "depleted_at")
                  if c in columns]
        rows = conn.execute("SELECT %s, data FROM bookmarks ORDER BY rowid"
                            % ", ".join(wanted)).fetchall()
        for row in rows:
            cols = dict(zip(wanted, row[:-1]))
            dump.rows.append({"id": cols.get("id"), "cols": cols,
                              "record": _record(row[-1])})
            if cols.get("system") and cols.get("system_address") not in (None, ""):
                dump.address_system.setdefault(cols["system_address"], str(cols["system"]))
        for system, address in _table_rows(conn, "bodies", ("system", "system_address")):
            if system and address not in (None, ""):
                dump.address_system.setdefault(address, str(system))
        dump.marks = _marks_from(_table_rows(conn, "meta", ("key", "value")))

        def system_of(address, body):
            if address in dump.address_system:
                return dump.address_system[address]
            named = {str(r["cols"].get("system") or "") for r in dump.rows
                     if str(r["cols"].get("planet_name") or "").lower()
                     == str(body or "").lower()} - {""}
            return named.pop() if len(named) == 1 else ""
        for row in _table_rows(conn, "maps", ("body", "name", "system_address",
                                              "body_id", "saved", "data")):
            entry = _map_entry(row, system_of)
            if entry is None:
                dump.skipped_maps += 1
            else:
                dump.maps.append(entry)
    except (sqlite3.Error, OSError) as problem:
        dump.error = "Could not read that database: %s" % problem
        return dump
    finally:
        if conn is not None:
            conn.close()
        clean()
    dump.pictures = pictures_beside(path)
    return dump
