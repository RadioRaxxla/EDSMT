"""Everything a commander has recorded, in the order a person reads it:
system, body, mining location, deposit.

The records are the survey's: its deposits and its logged locations. This
turns them into the rows one window needs - the systems, the bodies of a
system, the locations on a body, and the deposits in a location with their
rigs, where each is from the location's centre, what has been mined from
it and what is thought to be left.

Pure. It is handed the records and returns plain rows; it opens no window,
reads no file, asks nothing of the network and changes nothing.

1.10042 (the data window): the systems carry their rigs and tonnes, the
bodies are grouped by kind of ground, the locations on a body fold open and
shut with a line about each and how far it is from you, a location's
deposits come top patch first and worked out last, a worked-out deposit
says what it gave, and a deposit's card is put together here.
"""
import planview as PV
import survey as SV

MEASURED = "measured"   # from this deposit's own worked-out cycles
YOURS = "yours"         # from the commander's other deposits like it
CROWD = "crowd"         # from everyone's reports, five or more alike (1.10042)


def _folded(names):
    return {SV.fold(SV.canonical(name) or name) for name in names or () if SV.fold(name)}


def _has(names, picked):
    """True when nothing is picked, or any of `names` is one of those picked."""
    return not picked or bool(picked & _folded(names))


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _whole(value):
    return max(0, int(_number(value)))


def _natural(value):
    text = str(value or "").strip()
    try:
        return (0, float(text), "")
    except ValueError:
        return (1, 0.0, text.lower())


def _body_order(system, body):
    """Bodies in the order the game names them: A 1, A 2, A 10, B 3 a."""
    parts = SV.short_body(system, body).split()
    return [_natural(part) for part in parts]


def _named(row):
    return bool(str(row.get("system") or "").strip() and str(row.get("body") or "").strip())


def _places(store, picked=()):
    """Every location with something recorded, as {(system, body, number):
    {...}}, keyed in folded text. A logged signal with nothing marked is one;
    so is a find whose signal was never logged."""
    picked = _folded(picked)
    places = {}

    def place(row):
        key = (SV.fold(row.get("system")), SV.fold(row.get("body")),
               str(row.get("location") or "").strip())
        if key not in places:
            places[key] = {"system": str(row.get("system") or "").strip(),
                           "body": str(row.get("body") or "").strip(),
                           "location": key[2], "logged": False, "centre": None,
                           "offers": [], "worked_out": [], "found": [],
                           "deposits": 0, "intact": 0, "rigs": 0, "mined": 0,
                           "types": {}, "last": "", "ground": ""}
        return places[key]

    def ground(site, row):
        if not site["ground"] and str(row.get("planet_class") or "").strip():
            site["ground"] = SV.ground_of(row.get("planet_class"), row.get("volcanism"))

    for row in getattr(store, "locations", None) or []:
        if not _named(row):
            continue
        site = place(row)
        ground(site, row)
        site["logged"] = True
        site["offers"] = list(SV.Survey.offered(row))
        site["worked_out"] = list(SV.Survey.worked_out(row))
        site["last"] = max(site["last"], str(row.get("recorded") or ""))
        try:
            site["centre"] = (float(row["lat"]), float(row["lon"]))
        except (TypeError, ValueError, KeyError):
            site["centre"] = None
    for row in getattr(store, "deposits", None) or []:
        if not _named(row):
            continue
        site = place(row)
        ground(site, row)
        name = str(row.get("commodity") or "").strip() or "unknown"
        site["found"].append(name)
        if picked and not _has([name], picked):
            continue
        site["deposits"] += 1
        site["mined"] += mined_from(row)
        site["last"] = max(site["last"], str(row.get("recorded") or ""))
        if SV.is_depleted(row.get("amount")):
            continue
        site["intact"] += 1
        site["types"][name] = site["types"].get(name, 0) + 1
        site["rigs"] += _whole(row.get("rigs"))
    if picked:
        places = {key: site for key, site in places.items()
                  if _has(site["offers"] + site["found"], picked)}
    for site in places.values():
        site["types"] = dict(sorted(site["types"].items(),
                                    key=lambda pair: (-pair[1], pair[0].lower())))
    return places


def _merge_types(sites):
    types = {}
    for site in sites:
        for name, count in site["types"].items():
            types[name] = types.get(name, 0) + count
    return dict(sorted(types.items(), key=lambda pair: (-pair[1], pair[0].lower())))


def systems(store, picked=()):
    """One row a system that has anything recorded, in name order: how many
    bodies, locations and deposits, how many deposits are not worked out,
    and when it was last added to. `picked` keeps only what carries any of
    those commodities."""
    out = {}
    for site in _places(store, picked).values():
        row = out.setdefault(SV.fold(site["system"]), {
            "system": site["system"], "bodies": set(), "locations": 0,
            "deposits": 0, "intact": 0, "rigs": 0, "mined": 0, "last": ""})
        row["bodies"].add(SV.fold(site["body"]))
        row["locations"] += 1
        row["deposits"] += site["deposits"]
        row["intact"] += site["intact"]
        row["rigs"] += site["rigs"]
        row["mined"] += site["mined"]
        row["last"] = max(row["last"], site["last"])
    rows = sorted(out.values(), key=lambda row: row["system"].lower())
    for row in rows:
        row["bodies"] = len(row["bodies"])
    return rows


def totals(rows):
    """The foot of the systems list: systems, bodies, locations, deposits,
    the rigs still to be had and the tonnes mined."""
    return {"systems": len(rows),
            "bodies": sum(row["bodies"] for row in rows),
            "locations": sum(row["locations"] for row in rows),
            "deposits": sum(row["deposits"] for row in rows),
            "rigs": sum(row.get("rigs", 0) for row in rows),
            "mined": sum(row.get("mined", 0) for row in rows)}


def totals_text(total):
    """"3 systems - 7 locations - 12 deposits - 40 rigs - 1,240t mined"."""
    def count(number, word):
        return "{:,} {}{}".format(number, word, "" if number == 1 else "s")
    parts = [count(total["systems"], "system"), count(total["locations"], "location"),
             count(total["deposits"], "deposit")]
    if total.get("rigs"):
        parts.append(count(total["rigs"], "rig"))
    if total.get("mined"):
        parts.append("{:,}t mined".format(total["mined"]))
    return " - ".join(parts)


def mined_from(deposit):
    """Every tonne of its own commodity taken off a deposit: this time, and
    each time it was worked out before."""
    own, _others = SV.own_tonnes(deposit)
    return own + sum(SV.cycle_tonnes(deposit))


def bodies(store, system, picked=()):
    """One row a body of `system`, in the order the game numbers them."""
    want = SV.fold(system)
    out = {}
    for site in _places(store, picked).values():
        if SV.fold(site["system"]) != want:
            continue
        row = out.setdefault(SV.fold(site["body"]), {
            "system": site["system"], "body": site["body"],
            "short": SV.short_body(site["system"], site["body"]),
            "locations": 0, "deposits": 0, "intact": 0, "rigs": 0, "mined": 0,
            "sites": [], "last": "", "ground": ""})
        row["locations"] += 1
        row["deposits"] += site["deposits"]
        row["intact"] += site["intact"]
        row["rigs"] += site["rigs"]
        row["mined"] += site["mined"]
        row["ground"] = row["ground"] or site["ground"]
        row["sites"].append(site)
        row["last"] = max(row["last"], site["last"])
    rows = sorted(out.values(), key=lambda row: _body_order(row["system"], row["body"]))
    for row in rows:
        row["types"] = _merge_types(row.pop("sites"))
    return rows


UNKNOWN_GROUND = "Ground not known"


def grounds(store, system, picked=(), lookup=None):
    """The bodies of `system` grouped by the kind of ground they are:
    [{"ground", "bodies", "locations", "deposits", "rigs"}].

    A body's ground is what its own records say (body class and
    volcanism); failing that `lookup(system, body)` - the app's book of
    bodies - may give (planet class, volcanism). The group with the most
    deposits comes first, a body nobody described goes last under
    UNKNOWN_GROUND, and the bodies in a group are in the game's order."""
    groups = {}
    for row in bodies(store, system, picked):
        ground = row["ground"]
        if not ground and lookup is not None:
            try:
                found = lookup(row["system"], row["body"])
            except Exception:       # noqa: BLE001 - a book that cannot answer is no answer
                found = None
            if found and str(found[0] or "").strip():
                ground = SV.ground_of(found[0], found[1] if len(found) > 1 else "")
        ground = ground or UNKNOWN_GROUND
        row["ground"] = ground
        group = groups.setdefault(ground, {"ground": ground, "bodies": [], "locations": 0,
                                           "deposits": 0, "rigs": 0})
        group["bodies"].append(row)
        group["locations"] += row["locations"]
        group["deposits"] += row["deposits"]
        group["rigs"] += row["rigs"]
    return sorted(groups.values(), key=lambda group: (
        group["ground"] == UNKNOWN_GROUND, -group["deposits"], -group["rigs"],
        group["ground"].lower()))


def ground_rows(groups):
    """The grouped bodies as the rows of one list: a heading row for each
    ground ({"kind": "ground"}), then its bodies ({"kind": "body"})."""
    rows = []
    for group in groups:
        rows.append(dict(group, kind="ground"))
        rows.extend(dict(body, kind="body") for body in group["bodies"])
    return rows


def locations(store, system, body, picked=()):
    """One row a mining location on `body`, by its number."""
    want = (SV.fold(system), SV.fold(body))
    rows = [dict(site) for key, site in _places(store, picked).items() if key[:2] == want]
    for row in rows:
        del row["found"]
    return sorted(rows, key=lambda row: _natural(row["location"]))


def from_centre(store, deposit):
    """(metres, bearing) of a deposit from where its location was logged, or
    (None, None) when the location was never logged with a position or the
    deposit has none."""
    try:
        row = store.location(deposit.get("system"), deposit.get("body"),
                             deposit.get("location"))
        if not row:
            return None, None
        lat0, lon0 = float(row["lat"]), float(row["lon"])
        lat1, lon1 = float(deposit["lat"]), float(deposit["lon"])
        radius = float(row.get("radius_m") or 0) or 1e6
    except (TypeError, ValueError, KeyError, AttributeError):
        return None, None
    return (SV.surface_range_m(lat0, lon0, lat1, lon1, radius),
            SV.bearing_deg(lat0, lon0, lat1, lon1))


def holds(deposit, peers=None, crowd=None):
    """(low, high, how many, where from) tonnes this deposit holds when it is
    full, or None when that is not known.

    The commander's own figure first, when this deposit has been worked out
    before: what it gave each time. Otherwise the range everyone's reports
    give for deposits like it (`crowd`, once five alike have been worked out,
    1.10042). Otherwise from `peers` - the commander's other deposits - when
    one with the same rigs and Density has been. Never a formula."""
    held = SV.cycle_tonnes(deposit)
    if held:
        return min(held), max(held), len(held), MEASURED
    seen = crowd.range_for(deposit.get("commodity"), deposit.get("rigs"),
                           deposit.get("density")) if crowd is not None else None
    if seen:
        return seen[0], seen[1], seen[2], CROWD
    guess = SV.estimate_tonnes(peers, deposit.get("rigs"), deposit.get("density"),
                               exclude=deposit) if peers else None
    if guess:
        return guess[0], guess[1], guess[2], YOURS
    return None


def left(deposit, peers=None, crowd=None):
    """(low, high, how many, where from) tonnes thought to be left in it now:
    what it holds, less its own commodity mined from it since it was last
    worked out. None when what it holds is not known, or it is worked out."""
    if SV.is_depleted(deposit.get("amount")):
        return None
    full = holds(deposit, peers, crowd)
    if not full:
        return None
    own, _others = SV.own_tonnes(deposit)
    return max(0, full[0] - own), max(0, full[1] - own), full[2], full[3]


def body_radius(store, system, body):
    """The body's radius in metres from any location logged on it, or None."""
    for row in getattr(store, "locations", None) or []:
        if SV.fold(row.get("system")) == SV.fold(system) and SV.fold(row.get("body")) == SV.fold(body):
            radius = _number(row.get("radius_m"), 0.0)
            if radius > 0:
                return radius
    return None


def last_cycle(deposit):
    """The tonnes of its own commodity it gave the last time it was worked
    out, or None when it never was."""
    held = SV.cycle_tonnes(deposit)
    return held[-1] if held else None


def deposits(store, system, body, location=None, picked=(), radius_m=None, crowd=None):
    """One row a deposit on `body` - in one location, or in all of them -
    location by location, each location top patch first (see patch_order).
    `radius_m` is how wide a top patch is; the map's own by default. `crowd`
    is what everyone's reports say deposits hold (tonnesleft.TonnesBook)."""
    picked = _folded(picked)
    peers = getattr(store, "deposits", None) or []
    rows = []
    for deposit in store.at(system, body, location):
        name = str(deposit.get("commodity") or "").strip() or "unknown"
        if not _has([name], picked):
            continue
        metres, bearing = from_centre(store, deposit)
        own, others = SV.own_tonnes(deposit)
        spent = SV.is_depleted(deposit.get("amount"))
        rows.append({
            "kind": "deposit",
            "id": deposit.get("id"), "deposit": deposit,
            "location": str(deposit.get("location") or "").strip(),
            "commodity": name,
            "rigs": _whole(deposit.get("rigs")), "fit": _whole(deposit.get("rigs_fit")),
            "amount": str(deposit.get("amount") or "").strip(),
            "density": str(deposit.get("density") or "").strip(),
            "depleted": spent,
            "metres": metres, "bearing": bearing,
            "mined": own, "by": others,
            "holds": holds(deposit, peers, crowd), "left": left(deposit, peers, crowd),
            "gave": last_cycle(deposit) if spent else None,
            "recorded": str(deposit.get("recorded") or ""),
            "patch": 0,
        })
    radius = body_radius(store, system, body)
    out = []
    for number in sorted({row["location"] for row in rows}, key=_natural):
        out.extend(patch_order([row for row in rows if row["location"] == number],
                               body_m=radius, radius_m=radius_m))
    return out


def patch_order(rows, body_m=None, radius_m=None):
    """A location's deposit rows, the way they are worked: the top patch
    first - the knot with the most rigs, the deposit at its heart and then
    the rest of it nearest that one - then the next patch, then the
    deposits in no patch, most rigs first, and the worked-out ones last. Each row gets
    its patch number in "patch" (0 for none).

    The patches are the map's own top patches (planview.golden_groups), so
    the list and the circles on the map agree. Without the body's radius
    nothing can be measured and the rows go most rigs first."""
    def nearest(row):
        return (row["metres"] is None, row["metres"] or 0.0, row["commodity"].lower())

    live = [row for row in rows if not row["depleted"]]
    spent = sorted((row for row in rows if row["depleted"]), key=nearest)
    for row in rows:
        row["patch"] = 0
    groups = []
    if body_m and len(live) > 1:
        origin = None
        items = []
        for row in live:
            try:
                lat, lon = float(row["deposit"]["lat"]), float(row["deposit"]["lon"])
            except (TypeError, ValueError, KeyError):
                continue
            origin = origin or (lat, lon)
            east, north = SV.local_offset(origin[0], origin[1], lat, lon, body_m)
            items.append({"deposit": row["deposit"], "commodity": row["commodity"],
                          "east_m": east, "north_m": north,
                          "range_m": (east * east + north * north) ** 0.5, "row": row})
        radius = PV.golden_radius(radius_m) if radius_m else PV.GOLDEN_RADIUS_M
        groups = PV.golden_groups(items, {}, radius_m=radius, limit=len(items))
    ordered, taken = [], set()
    for number, group in enumerate(groups, 1):
        centre = group["centre"]
        members = sorted(group["items"], key=lambda item: (
            item is not centre,
            (item["east_m"] - centre["east_m"]) ** 2 + (item["north_m"] - centre["north_m"]) ** 2))
        for item in members:
            if id(item["row"]) in taken:
                continue
            taken.add(id(item["row"]))
            item["row"]["patch"] = number
            ordered.append(item["row"])
    rest = sorted((row for row in live if id(row) not in taken),
                  key=lambda row: (-row["rigs"],) + nearest(row))
    return ordered + rest + spent


# -- the locations on a body, folding ---------------------------------------

def _position(row):
    try:
        return float(row["lat"]), float(row["lon"])
    except (TypeError, ValueError, KeyError):
        return None


def from_you(store, system, body, location, you):
    """How far a location is from where you are now, when that can be
    known: ("m", metres) on its own body with a position - to its nearest
    deposit with one, else to where it was logged; ("ly", light years) in
    another system when both stars are known; (None, None) otherwise.

    `you` is {"system", "body", "lat", "lon", "radius_m", "ly"}; "ly", when
    there, answers the light years from you to a system, or None."""
    if not you:
        return None, None
    if SV.fold(you.get("system")) != SV.fold(system):
        ly = you.get("ly")
        try:
            far = ly(system) if ly is not None else None
        except Exception:       # noqa: BLE001 - a lookup that fails is not known
            far = None
        return ("ly", float(far)) if far is not None else (None, None)
    if SV.fold(you.get("body")) != SV.fold(body):
        return None, None
    try:
        lat, lon = float(you["lat"]), float(you["lon"])
        radius = float(you.get("radius_m") or 0) or body_radius(store, system, body)
    except (TypeError, ValueError, KeyError):
        return None, None
    if not radius:
        return None, None
    points = [_position(d) for d in store.at(system, body, location)]
    points = [p for p in points if p is not None]
    if not points:
        logged = store.location(system, body, location) if location else None
        point = _position(logged or {})
        points = [point] if point else []
    if not points:
        return None, None
    return "m", min(SV.surface_range_m(lat, lon, p[0], p[1], radius) for p in points)


def away_text(away, metres_text):
    """"820 m from you", "12.4 Ly from you", or "" when it is not known."""
    kind, value = away if away else (None, None)
    if kind == "m":
        return "%s from you" % metres_text(value)
    if kind == "ly":
        return "%.1f Ly from you" % value
    return ""


def location_line(site, rows, prices=None):
    """One line about a location: "Location 1 - 3 deposits, 10 rigs -
    Iridium, Rhodplumsite - 1 worked out". Its three most valuable
    commodities still to be had, or what the signal offers when nothing is
    marked there yet."""
    name = "Location %s" % site["location"] if site["location"] else "No location logged"
    if not rows:
        offers = SV.by_value(site.get("offers") or [], prices)[:3]
        return "%s - nothing marked%s" % (name, " - offers " + ", ".join(offers) if offers else "")
    count = "%d deposit%s" % (len(rows), "" if len(rows) == 1 else "s")
    rigs = sum(row["rigs"] for row in rows if not row["depleted"])
    if rigs:
        count += ", %d rig%s" % (rigs, "" if rigs == 1 else "s")
    names = []
    for row in rows:
        if not row["depleted"] and row["commodity"] not in names:
            names.append(row["commodity"])
    parts = [name, count]
    if names:
        parts.append(", ".join(SV.by_value(names, prices)[:3]))
    spent = sum(1 for row in rows if row["depleted"])
    if spent:
        parts.append("%d worked out" % spent)
    return " - ".join(parts)


def fold_rows(store, system, body, opened=(), picked=(), you=None, prices=None,
              radius_m=None):
    """The locations on a body as one list that folds: a line for each
    location ({"kind": "location"}: its line, how far it is from you,
    whether it is open), and under each open one its deposits in the
    order patch_order gives. `opened` holds the location numbers open."""
    opened = {str(number) for number in opened or ()}
    out = []
    for site in locations(store, system, body, picked):
        rows = deposits(store, system, body, site["location"], picked, radius_m)
        line = {"kind": "location", "location": site["location"], "site": site,
                "system": site["system"], "body": site["body"],
                "open": site["location"] in opened, "rows": rows,
                "rigs": sum(row["rigs"] for row in rows if not row["depleted"]),
                "mined": sum(row["mined"] for row in rows),
                "away": from_you(store, system, body, site["location"], you),
                "line": location_line(site, rows, prices)}
        out.append(line)
        if line["open"]:
            out.extend(rows)
    return out


# -- a picture of a site, and the surveyed areas of a body -------------------

def areas(maps):
    """The surveyed areas of a body, one row each that has ground swept in
    it: its number, the location it was driven for, the square kilometres
    swept, how much of its border that is (None with no border), when it
    was last added to, and the map itself for its picture."""
    rows = []
    for number, cmap in enumerate(maps or [], 1):
        if getattr(cmap, "anchor", None) is None:
            continue
        try:
            cover = cmap.coverage()
        except Exception:       # noqa: BLE001 - an area that cannot be summed is still an area
            cover = {}
        rows.append({"n": number, "signal": str(getattr(cmap, "signal", "") or "").strip(),
                     "km2": float(cover.get("painted_km2") or 0.0),
                     "percent": cover.get("percent"),
                     "updated": str(getattr(cmap, "updated", "") or ""), "map": cmap})
    return rows


def area_line(row):
    """"Area 1 - location 3 - 2.4 km2 swept - 62% of its border - 2026-11-01"."""
    parts = ["Area %d" % row["n"]]
    if row["signal"]:
        parts.append("location %s" % row["signal"])
    parts.append("%.1f km2 swept" % row["km2"])
    if row["percent"] is not None:
        parts.append("%d%% of its border" % row["percent"])
    if row["updated"]:
        parts.append(row["updated"][:10])
    return " - ".join(parts)


def picture_inputs(store, system, body, location=None, area=None):
    """What a map picture of a site is drawn from, as the map picture takes
    it: {"rows", "signal", "anchor", "survey"}, or None when nothing there
    has a position or the body's size is not known.

    A location is measured from where it was logged (failing that, from
    its first deposit with a position); a surveyed area (`area`, one of the
    body's coverage maps) from its own centre, with its swept ground and
    border."""
    radius = body_radius(store, system, body) or _number(getattr(area, "radius_m", 0), 0.0)
    every = store.at(system, body)
    origin, anchor, survey, signal = None, None, None, str(location or "").strip()
    if area is not None:
        origin = getattr(area, "anchor", None)
        signal = str(getattr(area, "signal", "") or "").strip()
    elif signal:
        origin = _position(store.location(system, body, signal) or {})
        anchor = (0.0, 0.0) if origin else None
    if origin is None:
        mine = [d for d in every if not signal or str(d.get("location") or "").strip() == signal]
        origin = next((p for p in (_position(d) for d in mine) if p is not None), None)
    if origin is None or not radius:
        return None
    if area is not None:
        def rel(point):
            return SV.local_offset(origin[0], origin[1], point[0], point[1], radius)
        centre = getattr(area, "centre", None)
        try:
            cover = area.coverage()
        except Exception:       # noqa: BLE001 - drawn without the percentage
            cover = {}
        survey = {"scan_m": area.scan_m, "points": [rel(p) for p in area.points],
                  "centre": rel(centre) if centre else None,
                  "border_m": area.border_m, "rings": area.rings() if centre else [],
                  "percent": cover.get("percent")}
    return {"rows": SV.rows_near(every, origin[0], origin[1], radius),
            "signal": signal, "anchor": anchor, "survey": survey}


# -- a deposit's card -------------------------------------------------------

def card(row, you=None, prices=None, metres_text=None):
    """Everything about one deposit, for its card: {"title", "lines",
    "depleted"}, the lines being (label, words) in reading order. `you` is
    where you are now, as from_you takes it."""
    metres_text = metres_text or (lambda m: "%.0f m" % m)
    deposit = row["deposit"]
    lines = [("System", deposit.get("system") or "-"),
             ("Body", deposit.get("body") or "-")]
    spot = _position(deposit)
    lines.append(("Position", "%.6f, %.6f" % spot if spot else "no position recorded"))
    lines.append(("From you", _from_you_words(deposit, spot, you, metres_text)))
    rigs = str(row["rigs"]) if row["rigs"] else "not recorded"
    if row.get("fit"):
        rigs += " (%d fit)" % row["fit"]
    lines += [("Rigs", rigs), ("Amount", row["amount"] or "not recorded"),
              ("Density", row["density"] or "not recorded")]
    this_time = "%dt" % row["mined"] if row["mined"] else "none yet"
    if row.get("by"):
        this_time += " (and %s)" % ", ".join("%s %dt" % pair for pair in sorted(
            row["by"].items(), key=lambda pair: -pair[1]))
    lines.append(("Mined this time", this_time))
    if row["depleted"]:
        lines.append(("Left", left_text(None, True, row.get("gave"))))
    else:
        basis = left_basis(row["left"], deposit)
        lines.append(("Left", left_text(row["left"]) + (" - " + basis if basis else "")))
    price = SV.price_of(row["commodity"], prices)
    lines.append(("Price", "{:,.0f} Cr/t".format(price) if price else "not known"))
    marked = str(deposit.get("recorded") or "")
    lines.append(("Marked", (marked[:10] + " " + marked[11:16] + " UTC").strip()
                  if len(marked) >= 16 else (marked or "-")))
    if row["depleted"]:
        since = str(deposit.get("depleted_at") or "")[:10]
        lines.append(("State", "worked out" + (" since " + since if since else "")))
    else:
        lines.append(("State", "active"))
    title = "%s - %s" % (row["commodity"], ("location %s" % row["location"])
                         if row["location"] else "no location")
    return {"title": title, "lines": lines, "depleted": row["depleted"]}


def _from_you_words(deposit, spot, you, metres_text):
    if spot is None:
        return "not known - no position was recorded for it"
    if not you or not you.get("body"):
        return "not known - where you are is not known yet"
    if SV.fold(you.get("system")) != SV.fold(deposit.get("system")) or \
            SV.fold(you.get("body")) != SV.fold(deposit.get("body")):
        return "not on this body - you are at %s" % (you.get("body") or you.get("system"))
    try:
        lat, lon = float(you["lat"]), float(you["lon"])
        radius = float(you.get("radius_m") or 0)
    except (TypeError, ValueError, KeyError):
        return "on this body - no position from the game yet"
    if not radius:
        return "on this body - no position from the game yet"
    metres = SV.surface_range_m(lat, lon, spot[0], spot[1], radius)
    bearing = SV.bearing_deg(lat, lon, spot[0], spot[1])
    words = "%s %s %03.0f" % (metres_text(metres), SV.compass(bearing), bearing % 360)
    if you.get("heading") is not None:
        words += " - %s" % SV.turn_hint(you["heading"], bearing)
    return words


# -- the words -------------------------------------------------------------

def where_text(metres, bearing, metres_text):
    """"1.24 km NE 045": a deposit from its location's centre. `metres_text`
    is the window's own way of writing a distance."""
    if metres is None or bearing is None:
        return "-"
    if metres < 1:
        return "at the centre"
    return "%s %s %03.0f" % (metres_text(metres), SV.compass(bearing), bearing % 360)


def left_text(estimate, depleted=False, gave=None):
    """The Est. left cell. "about" is measured on this deposit; "est." rests
    on other deposits like it. A worked-out deposit says what it gave the
    last time, when that was counted: "worked out (340t)"."""
    if depleted:
        return "worked out (%dt)" % gave if gave else "worked out"
    if not estimate:
        return "not measured yet"
    low, high, _count, source = estimate
    size = "%dt" % high if low == high else "%d-%dt" % (low, high)
    return ("about " if source == MEASURED else "est. ") + size


def left_basis(estimate, deposit):
    """What the figure rests on, in a sentence, for the tip."""
    if not estimate:
        return ""
    _low, _high, count, source = estimate
    times = "%d time%s" % (count, "" if count == 1 else "s")
    if source == MEASURED:
        return "From the %s this deposit was worked out." % times
    if source == CROWD:
        return "From %d reports of a deposit with %s rigs and %s density worked out." % (
            count, _whole(deposit.get("rigs")), str(deposit.get("density") or "").strip() or "the same")
    return "From %s a deposit of yours with %s rigs and %s density was worked out." % (
        times, _whole(deposit.get("rigs")), str(deposit.get("density") or "").strip() or "the same")
