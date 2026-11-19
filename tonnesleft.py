"""Tonnes held and left, for everyone (1.10042, D1, D2, D4).

A deposit worked out tells the community map the tonnes it gave. The map
answers, for a commodity, a rig count and a Density, a range of tonnes once
five alike have been worked out, with how many reports are behind it. This
module holds those ranges in the app, finds what an install worked out
before this version (for the one catch-up send), and says what a report
carries. No window, no network: it is handed what it needs.
"""
import survey as SV

TAG = "tonnes"
LEAST = 5
NOT_MEASURED = "not measured yet"


def _key(commodity, rigs, density):
    try:
        number = int(float(rigs))
    except (TypeError, ValueError):
        return None
    name = SV.fold(SV.canonical(commodity or "") or commodity or "")
    kind = SV.fold(density)
    if number <= 0 or not name or not kind:
        return None
    return name, number, kind


def _whole(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TonnesBook:
    """The ranges the community map last gave: what a deposit of a commodity
    with so many rigs and a Density held when it was worked out."""

    def __init__(self):
        self.groups = {}

    def take(self, data):
        """Keep an answer: the list of groups, or one group. True when it
        held a range worth keeping."""
        if not isinstance(data, dict):
            return False
        items = data["groups"] if isinstance(data.get("groups"), list) else \
            ([data] if "commodity" in data else [])
        if not items and not isinstance(data.get("groups"), list):
            return False
        found = {}
        for item in items:
            if not isinstance(item, dict) or not item.get("measured"):
                continue
            key = _key(item.get("commodity"), item.get("rigs"), item.get("density"))
            low, high, count = (_whole(item.get(k)) for k in ("low", "high", "samples"))
            if key is None or low is None or high is None or not count or count < LEAST:
                continue
            found[key] = (min(low, high), max(low, high), count)
        if isinstance(data.get("groups"), list):
            self.groups = found
        else:
            self.groups.update(found)
        return True

    def range_for(self, commodity, rigs, density):
        """(low, high, how many reports), or None when fewer than five alike
        have been worked out."""
        key = _key(commodity, rigs, density)
        return self.groups.get(key) if key else None


def catchup(deposits):
    """Every worked-out time on file, as (deposit, tonnes, day): what this
    install worked out before the tonnes were shared. Cycles are
    "2026-09-20=56;2026-10-02=48"; nothing counted, or unreadable, is left
    out."""
    out = []
    for row in deposits or []:
        for chunk in str(row.get("cycles") or "").split(";"):
            day, _, count = chunk.rpartition("=")
            day = day.strip()
            if len(day) != 10 or day[4] != "-" or day[7] != "-":
                continue
            tonnes = _whole(count.strip())
            if tonnes and tonnes > 0:
                out.append((row, tonnes, day))
    return out


def report_fields(tonnes, day=""):
    """The fields a report adds for its tonnes: {} when there are none. The
    day goes only with a catch-up of an earlier working out."""
    count = _whole(tonnes)
    if not count or count <= 0:
        return {}
    out = {"tonnes": count}
    if day:
        out["tonnes_on"] = str(day)[:10]
    return out
