"""Guide me there, to any deposit of yours on any body (1.10042).

Picked on a deposit's card in the data window, a deposit stays the one the
overlay guides you to until you drive onto it or press Stop guiding -
across jumps, landings and a restart. On its own body the map and the
overlay point at it; anywhere else this says where it is and what to do
next, in plain words. A deposit that cannot be guided to says why.

Pure: the app hands in the deposit and where you are, and keeps what
to_settings() gives in its settings. Nothing here opens a window, reads a
file or changes a record.
"""
import survey as SV

SETTING = "guide_target"


def _text(value):
    return " ".join(str(value or "").split())


def _position(deposit):
    try:
        return float(deposit["lat"]), float(deposit["lon"])
    except (TypeError, ValueError, KeyError):
        return None


def why_not(deposit):
    """"" when the deposit can be guided to, or why not, in a sentence."""
    if not isinstance(deposit, dict) or not _text(deposit.get("id")):
        return "That deposit is not in your records, so there is nothing to guide you to."
    if not (_text(deposit.get("system")) and _text(deposit.get("body"))):
        return "No body was recorded for that deposit, so there is nowhere to guide you to."
    if _position(deposit) is None:
        return ("No position was recorded for that deposit, so there is nothing to "
                "point at. Mark it again standing on it and it can be guided to.")
    return ""


def target_of(deposit):
    """What is kept about the deposit being guided to, or None when it
    cannot be guided to (why_not says why)."""
    if why_not(deposit):
        return None
    lat, lon = _position(deposit)
    return {"id": _text(deposit.get("id")), "system": _text(deposit.get("system")),
            "body": _text(deposit.get("body")), "location": _text(deposit.get("location")),
            "commodity": _text(deposit.get("commodity")) or "unnamed", "lat": lat, "lon": lon}


def to_settings(target):
    """The target as settings keep it: a plain dict, or None for none."""
    return dict(target) if target else None


def from_settings(value):
    """A target read back from settings, or None when it is not one."""
    if not isinstance(value, dict):
        return None
    if not (_text(value.get("id")) and _text(value.get("system")) and _text(value.get("body"))):
        return None
    try:
        float(value.get("lat"))
        float(value.get("lon"))
    except (TypeError, ValueError):
        return None
    return dict(value)


def _what(target):
    where = "location %s" % target["location"] if target.get("location") else "no location"
    return "the %s deposit (%s)" % (target.get("commodity") or "unnamed", where)


def status(target, system="", body="", guiding=None):
    """(state, words) for the guiding now. `system` and `body` are where you
    are; `guiding` is the id the overlay is pointed at.

    state is "off" (not guiding, or it has ended: you got there, or picked
    another deposit), "on" (on its body: the map and overlay point at it),
    "body" (in its system, on another body or none), or "system" (in
    another system, or where you are is not known)."""
    if not target or str(guiding or "") != str(target.get("id") or ""):
        return "off", "Not guiding. Guide me there on a deposit's card starts it."
    what = _what(target)
    short = SV.short_body(target["system"], target["body"])
    if SV.fold(system) == SV.fold(target["system"]):
        if SV.fold(body) == SV.fold(target["body"]):
            return "on", ("Guiding you to %s - the map and the overlay point at it "
                          "until you get there." % what)
        return "body", ("Guiding you to %s on %s. You are %s: the overlay points at "
                        "it once you are on %s." % (
                            what, target["body"], ("at " + body) if body else "in the system",
                            short))
    here = ("You are in %s. " % system) if system else ""
    return "system", ("Guiding you to %s on %s, in %s. %sJump there and land on %s: the "
                      "overlay points at it on that body." % (
                          what, target["body"], target["system"], here, short))


def arrived_on_body(target, system, body):
    """True when you are on the target's body."""
    return bool(target) and SV.fold(system) == SV.fold(target.get("system")) \
        and SV.fold(body) == SV.fold(target.get("body"))
