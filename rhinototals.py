"""Your Rhinos' totals across every session, for Earnings (1.10042).

The wing link shares the ground swept, finds and rig pins - not tonnes or
credits - so there is no wing total to add up yet. What can be said is your
own Rhinos' total, from the per-Rhino detail each session keeps, and it is
labelled as that. Pure logic.
"""
import survey as SV


def totals(rows):
    """{"tonnes", "sessions", "rhinos": [{label, tonnes, sessions}]} over the
    sessions that know their Rhinos, biggest first. Never raises."""
    by_label = {}
    sessions = 0
    for row in rows or ():
        try:
            parts = SV.rhino_split(row)
        except Exception:
            parts = []
        if not parts:
            continue
        sessions += 1
        for part in parts:
            slot = by_label.setdefault(part["label"], {"label": part["label"],
                                                       "tonnes": 0, "sessions": 0})
            slot["tonnes"] += int(part["tonnes"])
            slot["sessions"] += 1
    rhinos = sorted(by_label.values(), key=lambda p: (-p["tonnes"], p["label"]))
    return {"tonnes": sum(p["tonnes"] for p in rhinos), "sessions": sessions,
            "rhinos": rhinos}


def line(rows, wing_on):
    """The text for the all-time summary, or "" for nothing to say.

    With the wing link on: your Rhinos' total, said to be yours, and that
    wingmates' tonnes are not shared. With it off: the split between your
    Rhinos, only when there is more than one."""
    found = totals(rows)
    if not found["sessions"]:
        return ""
    each = ", ".join("%s %d t" % (p["label"], p["tonnes"]) for p in found["rhinos"][:6])
    if wing_on:
        text = "Wing: your Rhinos %d t over %d session%s" % (
            found["tonnes"], found["sessions"], "" if found["sessions"] == 1 else "s")
        if len(found["rhinos"]) > 1:
            text += " (%s)" % each
        return text + ". Wingmates' tonnes are not shared over the wing link, so only yours are added up."
    if len(found["rhinos"]) < 2:
        return ""
    return "Your Rhinos: %s" % each
