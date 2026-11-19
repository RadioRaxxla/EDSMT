"""Bringing finds in from other tools (1.10035). Inbound only.

Four kinds of source, each recognised by what is inside it and never by what
it is called:

    Bookmark database (.db)   a database of bookmarks with one JSON record each
    Share lines               a short code per find, pasted from a chat
    Survey CSV                one row per marked deposit, 38 columns
    Map JSON                  one surveyed body, its deposits in a list

Every reader here was written from the layouts the other tools document or
write; none of their code is used. Where a layout does not say something - the
Survey CSV does not say how it spells an amount, the Map JSON does not carry a
commodity - the reader says so in the preview rather than guessing.

An import never changes a find that is already here. It reads, works out what
is new (same commodity within the duplicate distance of a find already held is
the same find), shows the count, makes a dated backup, and only then adds.

No window code, so every path can be driven by a test.
"""

import base64
import csv
import io
import json
import math
import os
import re
import time
import zlib

import importdb as IDB
import survey as SV

KIND_BOOKMARKS = "bookmarks"
KIND_LINES = "lines"
KIND_CSV = "csv"
KIND_MAP = "map"

LABELS = {
    KIND_BOOKMARKS: "Bookmark database (.db)",
    KIND_LINES: "Share lines",
    KIND_CSV: "Survey CSV",
    KIND_MAP: "Map JSON",
}

# What the Survey CSV's first row has to contain for it to be that file. The
# file has 38 columns; these are the ones an import reads.
CSV_COLUMNS = ("system", "body", "locationsignalnumber", "planetradiuskm",
               "centerlatitude", "centerlongitude", "commodity",
               "mineralamount", "density", "rigcount", "markerlatitude",
               "markerlongitude", "markercreatedutc")
CSV_REQUIRED = ("system", "body", "commodity", "markerlatitude",
                "markerlongitude")

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_CODE = 4000
MAX_NAME = 120
# The most rigs a site can be recorded as taking: two Rhinos' worth. A
# Rhino carries six; a good deposit takes more than one Rhino (1.10040).
SITE_RIGS = 12

_CODE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]{1,31}:"
                   r"([A-Za-z0-9_-]{20,%d}={0,2})" % MAX_CODE)

SKIP_NO_NAME = "no system or body"
SKIP_NO_POSITION = "no position"
SKIP_NO_COMMODITY = "commodity not named"
SKIP_CODE = "commodity given as a code this cannot read"
SKIP_EMPTY_MAP = "map with no deposits"
SKIP_UNREADABLE = "could not be read"
SKIP_LONG = "name too long"
SKIP_MAP_SYSTEM = "map whose system not found"

# A bookmark with no location number is filed here, never under signal 1.
NO_LOCATION = "no location recorded"
# A bookmark the other tool took from somebody's share line carries this name.
SHARED_COMMANDER = "@Import-Shared"
# What such a find is marked with here: kept for you, never sent.
NOT_MINE = "not yours (imported)"
# How near a painted point a bookmark lies for the map to be its map.
MAP_REACH_M = 2000.0
STATE_FILE = "import_state.json"


class Source:
    """What was read from a file or a paste, before anything is decided."""

    def __init__(self, kind="", label=""):
        self.kind = kind
        self.label = label
        self.finds = []          # normalised dicts, see _find()
        self.skipped = {}        # reason -> how many
        self.signals = {}        # (system, body, number) -> centre / radius
        self.rows = 0
        self.error = ""
        self.notes = []          # things the format does not say
        self.marks = []          # good and bad marks on locations
        self.maps = []           # surveyed maps: centre, border, ground
        self.ids = set()         # ids of every bookmark read, for what is new later
        self.pictures = []       # (body, name, path) of saved map pictures
        self.skipped_maps = 0

    def skip(self, reason, count=1):
        self.skipped[reason] = self.skipped.get(reason, 0) + count


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        found = float(str(value).strip()) if not isinstance(value, (int, float)) else float(value)
    except (TypeError, ValueError):
        return None
    return found if math.isfinite(found) else None


def _text(value):
    text = str(value if value is not None else "").strip()
    # A leading apostrophe is how a spreadsheet export keeps a cell that
    # starts with = + - or @ from being read as a formula.
    if len(text) > 1 and text[0] == "'" and text[1] in "=+-@":
        text = text[1:]
    return text


def _label_of(value, labels):
    """The spelling in `labels` that `value` folds to, else ""."""
    wanted = SV.fold(value)
    for label in labels:
        if SV.fold(label) == wanted:
            return label
    return ""


def _amount(value):
    return _label_of(value, SV.AMOUNT_TIERS)


def _density(value):
    return _label_of(value, ("Low", "Medium", "High"))


def _rigs(value, max_rigs):
    found = _number(value)
    if found is None or not 1 <= found <= max_rigs or found != int(found):
        return ""
    return str(int(found))


def _location(value):
    found = _number(value)
    if found is None or found != int(found) or not 1 <= found <= 999:
        return "1"
    return str(int(found))


def _stamp(value):
    """A date from a file as the UTC stamp the records use, or ""."""
    text = _text(value)
    if not text:
        return ""
    cut = text.replace(" ", "T")
    if cut.endswith("Z"):
        cut = cut[:-1]
    for tail in ("+00:00", "-00:00"):
        if cut.endswith(tail):
            cut = cut[:-len(tail)]
    cut = cut.split(".", 1)[0]
    found = SV._epoch(cut + "Z")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(found)) if found else ""


def _commodity(value):
    """(name, reason): the list's own spelling, or why it was not usable."""
    text = _text(value)
    if not text:
        return "", SKIP_NO_COMMODITY
    known = SV.known_commodity(text)
    if known:
        return known, ""
    if len(text) <= 3 and text.isalpha():
        return "", SKIP_CODE
    if len(text) > 60 or not any(c.isalpha() for c in text):
        return "", SKIP_NO_COMMODITY
    return SV.canonical(text), ""


def _find(source, system, body, commodity, lat, lon, location="1", rigs="",
          amount="", density="", radius_m=None, recorded="", depleted_at="",
          max_rigs=SITE_RIGS, default=""):
    """Normalise one find into the source, or count why not."""
    system, body = _text(system), _text(body)
    if not (system and body):
        return source.skip(SKIP_NO_NAME)
    if len(system) > MAX_NAME or len(body) > MAX_NAME:
        return source.skip(SKIP_LONG)
    lat, lon = _number(lat), _number(lon)
    if lat is None or lon is None or not -90.0 <= lat <= 90.0 \
            or not -180.0 <= lon <= 180.0:
        return source.skip(SKIP_NO_POSITION)
    name, reason = _commodity(commodity) if str(commodity or "").strip() \
        else ("", SKIP_NO_COMMODITY)
    radius = _number(radius_m)
    entry = {"system": system, "body": body, "location": _location(location),
             "commodity": name, "rigs": _rigs(rigs, max_rigs),
             "amount": _amount(amount), "density": _density(density),
             "lat": "%.6f" % lat, "lon": "%.6f" % lon,
             "radius_m": radius if radius and radius > 0 else None,
             "recorded": _stamp(recorded), "depleted_at": _stamp(depleted_at),
             "reason": reason}
    source.finds.append(entry)
    return entry


# ---------------------------------------------------------------------------
# Share lines
# ---------------------------------------------------------------------------

def decode_code(code):
    """The record inside one share code, or None.

    A code is URL-safe base64 of zlib-compressed JSON. The size it may
    inflate to is capped, so a crafted code cannot be used to fill memory."""
    try:
        raw = base64.urlsafe_b64decode(code + "=" * (-len(code) % 4))
        data = json.loads(zlib.decompressobj().decompress(raw, 16384).decode("utf-8"))
    except (ValueError, zlib.error, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("system", "planet_name", "commodity"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            return None
    if _number(data.get("latitude")) is None or _number(data.get("longitude")) is None:
        return None
    return data


def read_lines(text, max_rigs=SITE_RIGS):
    """Every find in pasted text. Chat around the codes is ignored; a code
    that does not decode is counted."""
    source = Source(KIND_LINES, LABELS[KIND_LINES])
    for match in _CODE.finditer(str(text or "")):
        source.rows += 1
        record = decode_code(match.group(1))
        if record is None:
            source.skip(SKIP_UNREADABLE)
            continue
        _find(source, record.get("system"), record.get("planet_name"),
              record.get("commodity"), record.get("latitude"),
              record.get("longitude"), record.get("location_index"),
              record.get("rigs"), record.get("amount"), record.get("density"),
              record.get("planet_radius"), max_rigs=max_rigs)
    if not source.rows:
        source.error = "No share lines found in that text."
    return source


# ---------------------------------------------------------------------------
# Bookmark database
# ---------------------------------------------------------------------------

def _stamps_of(value):
    """A list of dates from a record as ordered, distinct UTC stamps."""
    out = []
    for item in value if isinstance(value, list) else []:
        stamp = _stamp(item)
        if stamp and stamp not in out:
            out.append(stamp)
    return sorted(out)


def _worked(record, commodity):
    """What a record's tonnes say: (open tally text, last tonne's stamp,
    worked-out cycles [(day, tonnes)], how many of those began at High,
    notes for cycles that ended unmarked)."""
    data = record.get("yield")
    cycles = data.get("cycles") if isinstance(data, dict) else None
    cycles = [c for c in cycles if isinstance(c, dict)] if isinstance(cycles, list) else []
    mine = SV.fold(SV.canonical(commodity or ""))
    opened, last, worked, high, unmarked = "", "", [], 0, []
    for number, cycle in enumerate(cycles):
        tons = cycle.get("tons") if isinstance(cycle.get("tons"), dict) else {}
        tally = {}
        for name, count in tons.items():
            amount = _number(count)
            if amount is not None and amount > 0 and str(name).strip():
                tally[SV.canonical(str(name))] = int(amount)
        own = sum(n for name, n in tally.items() if SV.fold(name) == mine)
        ended = str(cycle.get("ended") or "")
        when = _stamp(cycle.get("ended_at")) or _stamp(cycle.get("to")) \
            or _stamp(cycle.get("from"))
        if not ended and number == len(cycles) - 1:
            opened = SV.pack_counts(tally)
            last = _stamp(cycle.get("to")) or _stamp(cycle.get("from"))
        elif ended == "depleted":
            if own > 0 and when:
                worked.append((when[:10], own))
                high += str(cycle.get("amount_at_start") or "") == "High"
        elif own > 0:
            unmarked.append((when, "A cycle of %d t that was not marked worked out" % own))
    return opened, last, worked, high, unmarked


def read_bookmarks(path, max_rigs=SITE_RIGS, force_fallback=False):
    """The bookmarks in a database file, with their tonnes, dates, marks and
    maps. Opened read-only: nothing in it is changed, and a file that is not a
    database of bookmarks is said so."""
    source = Source(KIND_BOOKMARKS, LABELS[KIND_BOOKMARKS])
    dump = IDB.read(path, force_fallback)
    if dump.error:
        source.error = dump.error
        return source
    source.marks = dump.marks
    source.skipped_maps = dump.skipped_maps
    source.pictures = dump.pictures
    for row in dump.rows:
        source.rows += 1
        if row["id"] is not None:
            source.ids.add(int(row["id"]))
        columns_part, record = row["cols"], row["record"]
        if record is None:
            source.skip(SKIP_UNREADABLE)
            continue

        def pick(key, column=None):
            value = record.get(key)
            return columns_part.get(column or key) if value in (None, "") else value
        depleted_at = pick("depleted_at")
        amount = pick("amount")
        if depleted_at:
            amount = "Depleted"
        raw_place = _number(pick("location_index"))
        entry = _find(source, pick("system"), pick("planet_name"), pick("commodity"),
                      record.get("latitude"), record.get("longitude"),
                      pick("location_index"), pick("rigs"), amount,
                      record.get("density"), record.get("planet_radius"),
                      recorded=record.get("marked_at"), depleted_at=depleted_at,
                      max_rigs=max_rigs)
        if entry is None:
            continue
        if raw_place is None or raw_place != int(raw_place) or not 1 <= raw_place <= 999:
            entry["location"] = NO_LOCATION
        entry["ext_id"] = row["id"]
        entry["not_mine"] = str(record.get("commander") or "").strip() == SHARED_COMMANDER
        entry["no_rigs"] = _number(pick("rigs")) == 0
        opened, last, worked, high, unmarked = _worked(record, entry["commodity"])
        entry["mined"], entry["mined_at"] = opened, last if opened else ""
        entry["cycles"] = ";".join("%s=%d" % item for item in worked)
        entry["cycles_high"], entry["cycles_n"] = high, len(worked)
        entry["rechecks"] = ";".join(_stamps_of(record.get("rechecks")))
        extra = list(unmarked)
        lifted = []
        for item in record.get("regrown") if isinstance(record.get("regrown"), list) else []:
            if isinstance(item, dict):
                was, came = _stamp(item.get("depleted_at")), _stamp(item.get("regrown_at"))
                if was or came:
                    lifted.append((was, came))
                    extra.append((came, "Grown back: the other tool took off the depleted mark"
                                  " it carried from %s" % (was[:10] or "an unknown date")))
        entry["regrown_n"] = len(lifted)
        if not entry["depleted_at"] and lifted:
            # Lifted since: active now, but the first date it was depleted is kept.
            firsts = sorted(was for was, _came in lifted if was)
            entry["depleted_at"] = firsts[0] if firsts else ""
        edited = _stamp(record.get("updated_at"))
        if edited:
            extra.append((edited, "Last edited in the other tool"))
        entry["notes_extra"] = extra
    _place_maps(source, dump)
    if not source.rows:
        source.error = "That database holds no bookmarks."
    return source


def _place_maps(source, dump):
    """The maps as the plan will use them: each on the signal it names, or
    on the one the bookmarks lying on it are filed under."""
    for item in dump.maps:
        if not item["system"] or not item["body"]:
            source.skip(SKIP_MAP_SYSTEM)
            continue
        item = dict(item)
        here = [f for f in source.finds if SV.fold(f["body"]) == SV.fold(item["body"])
                and SV.fold(f["system"]) == SV.fold(item["system"])]
        if not item["radius_m"]:
            item["radius_m"] = next((f["radius_m"] for f in here if f["radius_m"]), None)
        if not item["location"] and item["radius_m"]:
            sample = item["points"][::max(1, len(item["points"]) // 300)][:300]
            if item["centre"]:
                sample.append(item["centre"])
            lying = set()
            for find in here:
                if find["location"] == NO_LOCATION:
                    continue
                for lat, lon in sample:
                    if SV.surface_range_m(lat, lon, float(find["lat"]), float(find["lon"]),
                                          item["radius_m"]) <= MAP_REACH_M:
                        lying.add(find["location"])
                        break
            if len(lying) == 1:
                item["location"] = lying.pop()
        source.maps.append(item)


# ---------------------------------------------------------------------------
# Survey CSV
# ---------------------------------------------------------------------------

def _head(cell):
    """A header cell folded to letters and digits, so System, system and
    marker_latitude or Marker Latitude all read the same."""
    return re.sub(r"[^a-z0-9]", "", _text(cell).lstrip("\ufeff").lower())


def looks_like_csv(header):
    seen = {_head(cell) for cell in header or ()}
    return all(name in seen for name in CSV_REQUIRED)


def read_csv_text(text, max_rigs=SITE_RIGS):
    source = Source(KIND_CSV, LABELS[KIND_CSV])
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    if not looks_like_csv(header):
        source.error = "That is not a survey CSV: its first row lacks " \
                       "System, Body, Commodity and the marker position."
        return source
    names = [_head(cell) for cell in header]
    source.notes.append("The CSV does not say how it spells an amount or a "
                        "density; ones this does not recognise are left blank.")
    for line in reader:
        if not any(cell.strip() for cell in line):
            continue
        source.rows += 1
        row = dict(zip(names, line))
        radius = _number(row.get("planetradiuskm"))
        radius_m = radius * 1000.0 if radius and radius > 0 else None
        commodity = _text(row.get("commodity"))
        lat, lon = row.get("markerlatitude"), row.get("markerlongitude")
        if not commodity and not _text(lat) and not _text(lon):
            source.skip(SKIP_EMPTY_MAP)
            continue
        entry = _find(source, row.get("system"), row.get("body"), commodity,
                      lat, lon, row.get("locationsignalnumber"),
                      row.get("rigcount"), row.get("mineralamount"),
                      row.get("density"), radius_m,
                      recorded=row.get("markercreatedutc"), max_rigs=max_rigs)
        if entry is not None:
            centre = (_number(row.get("centerlatitude")),
                      _number(row.get("centerlongitude")))
            key = (entry["system"], entry["body"], entry["location"])
            if None not in centre and -90 <= centre[0] <= 90 and -180 <= centre[1] <= 180:
                source.signals.setdefault(key, {"lat": centre[0], "lon": centre[1],
                                                "radius_m": radius_m})
    if not source.rows:
        source.error = "That CSV has a header and no rows."
    return source


# ---------------------------------------------------------------------------
# Map JSON
# ---------------------------------------------------------------------------

def read_map_text(text, default_commodity="", max_rigs=SITE_RIGS):
    source = Source(KIND_MAP, LABELS[KIND_MAP])
    try:
        data = json.loads(text)
    except ValueError:
        source.error = "That is not valid JSON."
        return source
    if not isinstance(data, dict) or not isinstance(data.get("deposits"), list) \
            or not (data.get("system") or data.get("body")):
        source.error = "That JSON is not a surveyed-body map: it has no " \
                       "system, body and list of deposits."
        return source
    source.notes.append("A map file records where each deposit is and how many "
                        "rigs, not what it is: a deposit is taken as its name "
                        "when that is a commodity, and otherwise as the "
                        "commodity you pick.")
    system, body = data.get("system"), data.get("body")
    radius = _number(data.get("planet_radius"))
    number = _text(data.get("pml_id"))
    number = number if number.isdigit() else "1"
    if not data["deposits"]:
        source.skip(SKIP_EMPTY_MAP)
    for item in data["deposits"]:
        source.rows += 1
        if not isinstance(item, dict):
            source.skip(SKIP_UNREADABLE)
            continue
        named = SV.known_commodity(_text(item.get("name")))
        _find(source, system, body, named or default_commodity,
              item.get("lat"), item.get("lon"), number,
              item.get("rigs"), "", "", radius, max_rigs=max_rigs)
    centre = (_number(data.get("pml_center_lat")), _number(data.get("pml_center_lon")))
    if source.finds and None not in centre and -90 <= centre[0] <= 90 \
            and -180 <= centre[1] <= 180:
        first = source.finds[0]
        source.signals[(first["system"], first["body"], first["location"])] = {
            "lat": centre[0], "lon": centre[1],
            "radius_m": radius if radius and radius > 0 else None}
    return source


# ---------------------------------------------------------------------------
# Reading whatever it is
# ---------------------------------------------------------------------------

EXPECTED = ("a bookmark database (.db), share lines pasted from a chat, a "
            "survey CSV, or a surveyed-body map (.json)")


def _decode(raw):
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def read_text(text, default_commodity="", max_rigs=SITE_RIGS):
    """Pasted or loaded text: Map JSON, a survey CSV or share lines, by what
    it holds."""
    text = str(text or "")
    head = text.lstrip("﻿ \t\r\n")
    if head.startswith("{"):
        return read_map_text(head, default_commodity, max_rigs)
    first = head.split("\n", 1)[0]
    if "," in first and looks_like_csv(next(csv.reader([first]), [])):
        return read_csv_text(head, max_rigs)
    if _CODE.search(text):
        return read_lines(text, max_rigs)
    source = Source("", "")
    source.error = "Not recognised. This reads %s." % EXPECTED
    return source


def read_path(path, default_commodity="", max_rigs=SITE_RIGS):
    """A file, by its contents."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            head = handle.read(16)
    except OSError as problem:
        source = Source()
        source.error = "Could not read that file: %s" % problem
        return source
    if head.startswith(b"SQLite format 3\x00"):
        if size > MAX_FILE_BYTES:
            source = Source()
            source.error = "That database is too large to import."
            return source
        return read_bookmarks(path, max_rigs)
    if size > MAX_TEXT_BYTES:
        source = Source()
        source.error = "That file is too large to be one this reads."
        return source
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as problem:
        source = Source()
        source.error = "Could not read that file: %s" % problem
        return source
    return read_text(_decode(raw), default_commodity, max_rigs)


# ---------------------------------------------------------------------------
# Deciding what is new
# ---------------------------------------------------------------------------

def fingerprint(find):
    """The server's own duplicate rule: body, commodity and the position to
    three places."""
    return "|".join([SV.fold(find["system"]), SV.fold(find["body"]),
                     SV.fold(find["commodity"]),
                     "%.3f" % float(find["lat"]), "%.3f" % float(find["lon"])])


class Plan:
    """What an import would do, worked out against the records as they are."""

    def __init__(self, source, label=""):
        self.source = source
        self.label = label or source.label
        self.new = []
        self.known = []
        self.skipped = dict(source.skipped)
        self.marks = []          # marks of the other tool's that you have not made yourself
        self.marks_held = 0
        self.maps = []           # maps to bring in: dicts with a built CoverageMap
        self.maps_held = 0

    @property
    def has_work(self):
        """True when importing would add anything: finds, marks or maps."""
        return bool(self.new or self.marks or self.maps)

    def details(self):
        """The lines under the preview: what else comes in, what is kept
        apart, and what does not come in at all. Counts, each with its reason."""
        out = []
        new = self.new
        open_n = sum(1 for f in new if f.get("mined"))
        cycles = sum(f.get("cycles_n", 0) for f in new)
        high = sum(f.get("cycles_high", 0) for f in new)
        if open_n or cycles:
            out.append("Tonnes: %d deposit(s) with tonnes this cycle, %d cycle(s) worked "
                       "out (%d opened at High - only those measure what a deposit holds)."
                       % (open_n, cycles, high))
        lifted = sum(f.get("regrown_n", 0) for f in new)
        looks = sum(len([x for x in str(f.get("rechecks") or "").split(";") if x]) for f in new)
        if lifted or looks:
            out.append("Dates: %d taken off depleted by the other tool and kept as notes, "
                       "%d recheck(s)." % (lifted, looks))
        if self.marks or self.marks_held:
            up = sum(1 for m in self.marks if m["mark"] == "up")
            down = len(self.marks) - up
            text = ("Marks: %d good and %d bad, kept on this PC and never shared"
                    % (up, down))
            if self.marks_held:
                text += "; %d more are places you have already marked, left as you have them" \
                    % self.marks_held
            out.append(text + ".")
        if self.maps or self.maps_held:
            centres = sum(1 for m in self.maps if m["map"].centre is not None)
            borders = sum(1 for m in self.maps if m["map"].border_m is not None)
            points = sum(len(m["map"].points) for m in self.maps)
            text = ("Maps: %d map(s) - %d centre(s), %d border(s), %d painted point(s)"
                    % (len(self.maps), centres, borders, points))
            if self.maps_held:
                text += "; %d already here, left alone" % self.maps_held
            out.append(text + ".")
        nowhere = sum(1 for f in new if f["location"] == NO_LOCATION)
        if nowhere:
            out.append("%d with no location recorded: filed under that name, not under "
                       "signal 1, and not sent to the community map." % nowhere)
        strangers = sum(1 for f in new if f.get("not_mine"))
        if strangers:
            out.append("%d came to the other tool from other people: kept here, marked as "
                       "not yours, and never sent." % strangers)
        norigs = sum(1 for f in new if f.get("no_rigs"))
        if norigs:
            out.append("%d with no rigs: brought in without a rig count." % norigs)
        if self.source.kind == KIND_BOOKMARKS:
            out.append("Not brought in: its settings, its own body list, heading and "
                       "altitude, and tonnes refined away from any bookmark.")
        return out

    @property
    def counts(self):
        return len(self.new), len(self.known), sum(self.skipped.values())

    def preview(self):
        """"12 new, 3 already known, 2 skipped: no position (1), ..."."""
        new, known, skipped = self.counts
        text = "%d new, %d already known, %d skipped" % (new, known, skipped)
        if skipped:
            text += ": " + ", ".join("%s (%d)" % (reason, count) for reason, count
                                     in sorted(self.skipped.items(),
                                               key=lambda kv: (-kv[1], kv[0])))
        return text + "."


def _radius_for(find, store, held):
    if find["radius_m"]:
        return find["radius_m"]
    for row in store.locations_on(find["system"], find["body"]):
        try:
            found = float(row.get("radius_m") or 0)
        except (TypeError, ValueError):
            found = 0.0
        if found:
            return found
    for other in held:
        if other["radius_m"] and SV.fold(other["system"]) == SV.fold(find["system"]) \
                and SV.fold(other["body"]) == SV.fold(find["body"]):
            return other["radius_m"]
    return None


def _same_find(find, other, radius, within_m):
    """Same commodity, and within the duplicate distance - or, with no size
    for the body, the same to three places."""
    if SV.fold(other["commodity"]) != SV.fold(find["commodity"]):
        return False
    if fingerprint(find) == fingerprint(other):
        return True
    if not radius:
        return False
    try:
        return SV.surface_range_m(float(find["lat"]), float(find["lon"]),
                                  float(other["lat"]), float(other["lon"]),
                                  radius) <= within_m
    except (TypeError, ValueError, KeyError):
        return False


def make_plan(source, store, within_m=100.0, default_commodity="", marks=None,
              coverage=None):
    """Sort a source's finds into new, already known and skipped, and work out
    which marks and maps would come in beside them. `marks` is your own-marks
    book and `coverage` the book of maps; left out, those are not planned."""
    plan = Plan(source)
    _plan_marks(plan, source, marks)
    _plan_maps(plan, source, coverage)
    for find in source.finds:
        find = dict(find)
        if not find["commodity"] and find["reason"] == SKIP_NO_COMMODITY:
            tidy = SV.known_commodity(default_commodity) if default_commodity else ""
            if tidy:
                find["commodity"], find["reason"] = tidy, ""
        if find["reason"] or not find["commodity"]:
            plan.skipped[find["reason"] or SKIP_NO_COMMODITY] = \
                plan.skipped.get(find["reason"] or SKIP_NO_COMMODITY, 0) + 1
            continue
        radius = _radius_for(find, store, plan.new)
        held = (d for d in store.at(find["system"], find["body"]))
        if any(_same_find(find, other, radius, within_m) for other in held) \
                or any(_same_find(find, other, radius, within_m) for other in plan.new):
            plan.known.append(find)
        else:
            plan.new.append(find)
    return plan


def _plan_marks(plan, source, book):
    if book is None:
        return
    for item in source.marks:
        if book.mine(item["system"], item["body"], item["location"]):
            plan.marks_held += 1
        else:
            plan.marks.append(item)


def _plan_maps(plan, source, book):
    """Maps with an anchor, a place and nothing like them already held."""
    if book is None:
        return
    import coverage as CV
    for item in source.maps:
        cmap = CV.CoverageMap.from_dict({
            "system": item["system"], "body": item["body"],
            "radius_m": item["radius_m"], "points": item["points"],
            "centre": list(item["centre"]) if item["centre"] else None,
            "border_m": item["border_m"], "signal": item["location"]})
        anchor = cmap.anchor
        if anchor is None or not cmap.radius_m:
            plan.skipped["map with no size for its body"] = \
                plan.skipped.get("map with no size for its body", 0) + 1
            continue
        held = False
        for other in book.maps_on(item["system"], item["body"]):
            there = other.anchor
            if there is not None and SV.surface_range_m(
                    there[0], there[1], anchor[0], anchor[1], cmap.radius_m) <= CV.SAME_MAP_M:
                held = True
                break
        if held:
            plan.maps_held += 1
        else:
            plan.maps.append({"map": cmap, "item": item})


def sharing_line(settings, community, always=()):
    """What the preview says about sharing, from the settings that decide it.

    `always` is the app's list of settings that are on whatever a file says.
    Sharing is on when community_auto_share is one of those or is set, and
    only goes anywhere when the link is ready."""
    on = "community_auto_share" in always or bool(
        (settings or {}).get("community_auto_share", True))
    if not on:
        return "These finds will stay on this PC: sharing is off."
    if community is None or not getattr(community, "ready", False):
        return ("These finds will stay on this PC for now: the community link "
                "is not ready.")
    named = bool(getattr(community, "share_name", True))
    return ("These finds will be shared with the community map, as sharing "
            "is always on - %s." % ("under your CMDR name" if named
                                    else "without your name"))


def _notes_for(find, label):
    """The note a new deposit begins with, and a dated line for each thing the
    other tool said about it. The import line stays first: it is how a row an
    import made is told from one you logged."""
    note = SV.stamp_note("", "Imported from %s" % label)
    if find.get("not_mine"):
        note += "\nNot yours: the other tool had taken this from somebody else's shared line. Kept for you, never sent."
    if find["location"] == NO_LOCATION:
        note += "\nThe other tool had no location number for it."
    for when, text in sorted(find.get("notes_extra") or [], key=lambda item: item[0] or ""):
        epoch = SV._epoch(when) if when else 0
        note = SV.stamp_note(note, text, time.localtime(epoch) if epoch else None)
    return note


def _remember(state_path, plan):
    """Write down which bookmarks were seen, so the next look can say how many
    are new. Never raises: a note that cannot be kept costs only that."""
    if not state_path or plan.source.kind != KIND_BOOKMARKS or not plan.source.ids:
        return False
    try:
        folder = os.path.dirname(state_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(state_path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump({"ids": sorted(plan.source.ids), "at": SV.utc_now()}, handle)
        os.replace(state_path + ".tmp", state_path)
        return True
    except OSError:
        return False


def _copy_pictures(source, folder):
    """Copy the other tool's saved map pictures into `folder`. How many."""
    import shutil
    done = 0
    os.makedirs(folder, exist_ok=True)
    for body, name, path in source.pictures:
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in "%s %s" % (body, name))
        target = os.path.join(folder, "imported-%s" % safe)
        if os.path.exists(target):
            continue
        try:
            shutil.copyfile(path, target)
            done += 1
        except OSError:
            continue
    return done


def apply(plan, store, backup_folder, within_m=100.0, marks=None, coverage=None,
          state_path=None, pictures_folder=None, copy_pictures=False):
    """Add a plan's new finds, marks and maps, after a dated backup of
    everything held.

    Returns a result dict: ok, reason, backup (the zip's path), taken,
    signals, maps, marks, kept (finds kept for you and never sent), pictures,
    and records (the deposit rows added that may be shared). If the backup
    cannot be written nothing is imported: the one moment somebody else's
    file is allowed to change yours is the moment you must be able to undo
    it."""
    result = {"ok": False, "reason": "", "backup": "", "taken": 0,
              "signals": 0, "records": [], "maps": 0, "marks": 0, "kept": 0,
              "pictures": 0}
    if not plan.has_work:
        result["ok"] = True
        result["reason"] = "Nothing new to add."
        return result
    try:
        backup, _count = store.backup_to(backup_folder)
    except (OSError, ValueError) as problem:
        result["reason"] = ("Nothing was imported: the backup that comes "
                            "first could not be written (%s)." % problem)
        return result
    result["backup"] = backup or ""
    note = SV.stamp_note("", "Imported from %s" % plan.label)
    made = set()
    for find in plan.new:
        depleted = SV.is_depleted(find["amount"])
        first = find["depleted_at"]
        stored = store.add_deposit(
            system=find["system"], body=find["body"], location=find["location"],
            commodity=find["commodity"], rigs=find["rigs"], density=find["density"],
            amount=find["amount"], lat=find["lat"], lon=find["lon"],
            status=SV.STATUS_REPORTED, notes=_notes_for(find, plan.label),
            recorded=find["recorded"],
            depleted_at=(first or find["recorded"] or SV.utc_now()) if depleted else first,
            mined=find.get("mined") or "", mined_at=find.get("mined_at") or "",
            cycles=find.get("cycles") or "", rechecks=find.get("rechecks") or "",
            cmdr=NOT_MINE if find.get("not_mine") else "")
        if find.get("not_mine"):
            result["kept"] += 1
        else:
            result["records"].append(stored)
        result["taken"] += 1
        made.add((find["system"], find["body"], find["location"]))
    for item in plan.maps:
        if item["item"]["location"]:
            made.add((item["item"]["system"], item["item"]["body"], item["item"]["location"]))
    # A signal row so the body remembers the finds are in one. An existing
    # signal is never touched: an import must not move a centre somebody
    # stood on and logged themselves.
    centres = {}
    for item in plan.maps:
        info = item["item"]
        if info["location"] and info["centre"]:
            centres.setdefault((info["system"], info["body"], info["location"]),
                               {"lat": info["centre"][0], "lon": info["centre"][1],
                                "radius_m": info["radius_m"]})
    for system, body, number in sorted(made):
        if store.location(system, body, number) is not None:
            continue
        centre = centres.get((system, body, number)) \
            or plan.source.signals.get((system, body, number)) or {}
        radius = centre.get("radius_m") or next(
            (f["radius_m"] for f in plan.new if f["radius_m"]
             and (f["system"], f["body"]) == (system, body)), None)
        # Dated by what was imported, never by the import: the newest date
        # among this signal's finds, or none when the file gave none.
        seen = max((f["recorded"] or "" for f in plan.new
                    if (f["system"], f["body"], f["location"]) == (system, body, number)),
                   default="")
        store.set_location(system, body, number, lat=centre.get("lat"),
                           lon=centre.get("lon"), radius_m=radius, notes=note,
                           recorded=seen)
        result["signals"] += 1
    if marks is not None:
        for item in plan.marks:
            if marks.set(item["system"], item["body"], item["location"], item["mark"]):
                result["marks"] += 1
        if result["marks"]:
            marks.save()
    if coverage is not None:
        for item in plan.maps:
            cmap = item["map"]
            cmap.created = cmap.updated = SV.utc_now()
            if coverage.save(cmap):
                result["maps"] += 1
    if copy_pictures and pictures_folder:
        result["pictures"] = _copy_pictures(plan.source, pictures_folder)
    _remember(state_path, plan)
    result["ok"] = True
    return result


def new_since(state_path, path):
    """How many bookmarks the database at `path` holds that were not there at
    the last import, or None when there was no import or it cannot be read."""
    try:
        with open(state_path, encoding="utf-8") as handle:
            seen = {int(i) for i in json.load(handle).get("ids", [])}
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    now = IDB.bookmark_ids(path)
    if now is None:
        return None
    return len(now - seen)


def offer(state_path, found=None):
    """After a first import: {path, new, text} when the other tool has
    bookmarks that were not there at the last import, else None. It only
    says so; reading them is a click of the person's own."""
    for item in (found if found is not None else IDB.locate()):
        count = new_since(state_path, item["path"])
        if count:
            return {"path": item["path"], "new": count,
                    "text": "%d new since your last import" % count}
    return None


def community_rows(records):
    """Deposit rows as the community upload takes them, for finds that have a
    position. The galactic position is left off: it describes where the
    commander is, not where an imported find is."""
    out = []
    for record in records:
        if record.get("location") == NO_LOCATION or record.get("cmdr") == NOT_MINE:
            continue
        try:
            lat, lon = float(record["lat"]), float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "system": record["system"], "planet": record["body"],
            "spot": record["location"], "type": record["commodity"],
            "rigs": int(float(record.get("rigs") or 0)), "lat": lat, "lon": lon,
            "density": record.get("density") or "",
            "amount": record.get("amount") or "",
            "status": record.get("status") or SV.STATUS_REPORTED,
            "planet_class": "", "gravity": None, "atmosphere": "",
            "volcanism": "", "temperature_k": None, "notes": ""})
    return out


def summary(result, plan):
    """The one line said after an import."""
    if not result["ok"]:
        return result["reason"]
    if not result["taken"]:
        return "Nothing new to add - %s" % plan.preview()
    bits = ["Imported %d find(s) from %s" % (result["taken"], plan.label)]
    if result["signals"]:
        bits.append("%d mining location(s)" % result["signals"])
    new, known, skipped = plan.counts
    if known:
        bits.append("%d already known, left alone" % known)
    if skipped:
        bits.append("%d skipped" % skipped)
    if result["backup"]:
        bits.append("your records were backed up to %s first"
                    % os.path.basename(result["backup"]))
    return ". ".join(bits) + "."
