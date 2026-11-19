"""The extra lines on the overlay's STATUS box (1.10042): SRV fuel, tonnes
an hour, merits this session, and when the Rhino and the ship will be full
with how long a Rhino load takes (filltimer.py).

Each is worked out by the app from what it already reads and handed to the
overlay as one small dict, {"fuel": (text, warn), "tph": text, "merits":
text}. A line with nothing to say is left out, and each has a switch in
Settings. Pure functions, no window.
"""

# The setting that turns each line on, and the label it is drawn with.
SWITCHES = {"fuel": "overlay_status_fuel", "tph": "overlay_status_tph",
            "merits": "overlay_status_merits", "fill": "overlay_status_fill"}
LABELS = {"fuel": "SRV fuel", "tph": "t/h", "merits": "Merits",
          "rhino": "Rhino full", "ship": "Ship full", "load": "Rhino load"}
# The fill lines (rhino, ship, load) share the one switch, "fill".
FILL = ("rhino", "ship", "load")
ORDER = ("fuel", "tph", "merits") + FILL


def fuel_line(in_srv, fuel_main, low=False):
    """(text, warn) for the SRV's fuel, or None when not in the SRV or the
    game has not said. Tonnes as the game reports them; LOW when its own
    low-fuel flag is up."""
    if not in_srv:
        return None
    try:
        tonnes = float(fuel_main)
    except (TypeError, ValueError):
        return None
    if tonnes < 0:
        return None
    return ("%.2f t%s" % (tonnes, "  LOW" if low else ""), bool(low))


def tph_line(t_hr):
    """Tonnes refined an hour for the session under way, as Earnings shows
    it, or None when there is no session or nothing mined yet."""
    try:
        value = float(t_hr)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return "%.1f" % value


def merits_line(pledged, earned):
    """Merits the game has paid this session, only when a Power is pledged;
    None otherwise. Nought is said as 0 so the line shows the tracking is on."""
    if not str(pledged or "").strip():
        return None
    try:
        count = int(earned or 0)
    except (TypeError, ValueError):
        return None
    return "{:,}".format(max(0, count))


def build(settings, in_srv, fuel_main, low, t_hr, pledged, earned, fill=None):
    """The dict the overlay draws from, with only the switched-on lines that
    have something to say. `fill` is {"rhino", "ship", "load"} as filltimer
    words them."""
    settings = settings or {}
    out = {}
    if settings.get(SWITCHES["fuel"], True):
        line = fuel_line(in_srv, fuel_main, low)
        if line:
            out["fuel"] = line
    if settings.get(SWITCHES["tph"], True):
        line = tph_line(t_hr)
        if line:
            out["tph"] = line
    if settings.get(SWITCHES["merits"], True):
        line = merits_line(pledged, earned)
        if line:
            out["merits"] = line
    if settings.get(SWITCHES["fill"], True):
        for key in FILL:
            line = (fill or {}).get(key)
            if line:
                out[key] = line
    return out


def rows(lines):
    """[(label, value)] in drawing order for the readout."""
    out = []
    for key in ORDER:
        value = (lines or {}).get(key)
        if not value:
            continue
        text = value[0] if isinstance(value, tuple) else value
        out.append((LABELS[key], text))
    return out


def compact(lines):
    """(text, warn): the same lines as one short line, for a STATUS box with
    no room for a row each - "FUEL 0.30 t  9.0 T/H  40 MERITS". ("", False)
    with nothing to say. warn is the SRV's low-fuel flag."""
    parts, warn = [], False
    for key in ORDER:
        value = (lines or {}).get(key)
        if not value:
            continue
        if isinstance(value, tuple):
            text = value[0]
            warn = warn or bool(len(value) > 1 and value[1])
        else:
            text = value
        if key == "fuel":
            parts.append("FUEL %s" % text)
        elif key == "tph":
            parts.append("%s T/H" % text)
        elif key == "merits":
            parts.append("%s MERITS" % text)
        else:
            # Only the time, or FULL: the tonnes do not fit on one line.
            first = text.split("  ")[0].upper()
            parts.append({"rhino": "RHINO ", "ship": "SHIP ", "load": "LOAD "}[key] + first)
    return ("  ".join(parts), warn)
