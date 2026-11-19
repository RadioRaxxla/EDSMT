"""How full each rig is, counted from the journal (1.2).

The journal has no rig event. It writes one MiningRefined a tonne, and a rig
holds RIG_HOLDS_T. A tonne refined of a rig's commodity, in the Rhino that
put the rig down, after it went down, on that body, is put against that rig.
The count is exact when only one of that Rhino's rigs is on that commodity.
When several are, the tonne goes to the rig nearest where it was refined (to
the one with the fewest when that is not known) and those counts are marked
as estimates. A rig at RIG_HOLDS_T takes no more.

Pure: no window, no files, no sound.
"""
import survey as SV

RIG_HOLDS_T = 12


def _fold(name):
    return SV.fold(SV.canonical(name) or name) if name else ""


def _same_rhino(rig, srv):
    return srv is None or rig.get("srv") is None or str(rig.get("srv")) == str(srv)


def count(rig):
    """The tonnes put against a rig so far."""
    try:
        return max(0, int((rig or {}).get("t") or 0))
    except (TypeError, ValueError):
        return 0


def is_full(rig):
    return count(rig) >= RIG_HOLDS_T


def text(rig):
    """"8/12", or "~8/12" when the count is an estimate."""
    return "%s%d/%d" % ("~" if (rig or {}).get("guess") else "", count(rig), RIG_HOLDS_T)


def _away(rig, note):
    try:
        radius = float(note.get("radius_m") or 0) or 0.0
        if radius <= 0:
            return None
        return SV.surface_range_m(float(note["lat"]), float(note["lon"]),
                                  float(rig["lat"]), float(rig["lon"]), radius)
    except (KeyError, TypeError, ValueError):
        return None


def credit(rigs, note):
    """Put one refined tonne (the reader's "Refined" note: commodity, when,
    srv_id, lat, lon, radius_m, in_srv) against a rig in `rigs` - the app's
    rig records (n, lat, lon, at, commodity, srv) - adding one to its "t".
    The rig credited, or None."""
    if not isinstance(note, dict) or note.get("in_srv") is False:
        return None
    what = _fold(note.get("commodity"))
    if not what:
        return None
    when = SV._epoch(note.get("when"))
    srv = note.get("srv_id")
    picks = []
    for rig in rigs or ():
        if not isinstance(rig, dict) or _fold(rig.get("commodity")) != what:
            continue
        if not _same_rhino(rig, srv):
            continue
        try:
            put_down = float(rig.get("at") or 0)
        except (TypeError, ValueError):
            put_down = 0.0
        if when and put_down and put_down > when + 1:
            continue
        picks.append(rig)
    if not picks:
        return None
    open_ = [rig for rig in picks if not is_full(rig)]
    if not open_:
        return None
    if len(picks) > 1:
        for rig in picks:
            rig["guess"] = True

    def nearest(rig):
        away = _away(rig, note)
        return (away is None, away if away is not None else 0.0, count(rig), rig.get("n") or 0)

    rig = min(open_, key=nearest)
    rig["t"] = count(rig) + 1
    return rig
