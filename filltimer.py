"""How long the Rhino and the ship take to fill (1.10042).

Each Rhino load is timed from its first tonne to a full Rhino (72 t, the
most a Rhino has been seen to hold: shiphold.RHINO_HOLD_T). From the rate of
the load under way, or of the session, the STATUS box says when the Rhino
will be full and when the ship will be, by the ship's own cargo capacity
less what is in it and what the Rhino is carrying to it.

FillClock is told what the Rhino holds whenever the journal says, with the
time; it keeps the loads it has timed. The *_text functions are the words.
Pure: no window, no journal of its own.
"""

import shiphold as SH

RHINO_FULL_T = SH.RHINO_HOLD_T
# The average is of the newest loads: a different site or Rhino changes it.
LOADS_AVERAGED = 5
# A rate needs this much to go on, or the first few tonnes say nonsense.
RATE_MIN_T = 3
RATE_MIN_S = 60.0


class FillClock:
    """The Rhino's loads, timed. A load starts at its first tonne after the
    Rhino was empty and is timed when the Rhino is full; one unloaded before
    it was full, or joined part-way, is not a full load and is not timed."""

    def __init__(self, full=RHINO_FULL_T):
        self.full = int(full)
        self.loads = []          # seconds each full load took, oldest first
        self._last_t = None      # the Rhino's tonnes when last told
        self._start = None       # when the load under way had its first tonne
        self._first_t = 0        # the Rhino's tonnes then
        self._whole = False      # it began from an empty Rhino
        self._timed = False      # this load has been timed already

    def note(self, rhino_t, when):
        """What the Rhino holds now, and the time (seconds). None - the
        journal has not said - is ignored."""
        if rhino_t is None:
            return
        try:
            tonnes = max(0, int(rhino_t))
            when = float(when)
        except (TypeError, ValueError):
            return
        before = self._last_t
        self._last_t = tonnes
        if before is None:
            return
        if tonnes < before:
            # Unloaded, or lost: whatever was under way is over.
            self._start, self._timed = None, False
            return
        if tonnes > before and self._start is None:
            self._start, self._first_t = when, tonnes
            self._whole, self._timed = before == 0, False
        if (tonnes >= self.full and self._start is not None and self._whole
                and not self._timed):
            self.loads.append(max(0.0, when - self._start))
            self._timed = True

    def loads_timed(self):
        return len(self.loads)

    def last_load(self):
        """Seconds the newest full load took, or None."""
        return self.loads[-1] if self.loads else None

    def average(self):
        """Seconds a full load takes, over the newest few, or None."""
        recent = self.loads[-LOADS_AVERAGED:]
        return sum(recent) / len(recent) if recent else None

    def this_load(self, now):
        """(seconds since its first tonne, tonnes in the Rhino) for the load
        under way, or None."""
        if self._start is None or self._last_t is None:
            return None
        return max(0.0, float(now) - self._start), self._last_t

    def rate(self, now):
        """Tonnes an hour of the load under way, or None with too little to
        go on."""
        under = self.this_load(now)
        if under is None:
            return None
        elapsed, tonnes = under
        added = tonnes - self._first_t
        if added < RATE_MIN_T or elapsed < RATE_MIN_S:
            return None
        return added / elapsed * 3600.0


def span_text(seconds):
    """"24m", "3h 10m", "<1m"; "" for nothing."""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds != seconds or seconds < 0:
        return ""
    if seconds < 30:
        return "<1m"
    minutes = int(round(seconds / 60.0))
    if minutes < 60:
        return "%dm" % minutes
    return "%dh %02dm" % divmod(minutes, 60)


def _hours_to(tonnes, rate):
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return None
    return tonnes / rate * 3600.0 if rate > 0 else None


def rhino_text(rhino_t, rate, full=RHINO_FULL_T):
    """"in 11m  40/72 t", "FULL  72/72 t", "10/72 t" with no rate yet, or
    None when the journal has not said what the Rhino holds."""
    if rhino_t is None:
        return None
    held = max(0, int(rhino_t))
    if held >= full:
        return "FULL  %d/%d t" % (held, full)
    seconds = _hours_to(full - held, rate)
    if seconds is None:
        return "%d/%d t" % (held, full)
    return "in %s  %d/%d t" % (span_text(seconds), held, full)


def ship_text(card, rhino_t, rate):
    """When the ship will be full, from its hold card (shiphold.hold_card):
    "in 5h 00m  300/1227 t", "FULL with this load", "FULL", or what it holds
    with no rate yet. None when the hold or its capacity is not known."""
    if not card or not card.get("known") or not card.get("capacity"):
        return None
    tonnes, capacity = int(card.get("tonnes") or 0), int(card["capacity"])
    if tonnes >= capacity:
        return "FULL"
    to_fill = capacity - tonnes - max(0, int(rhino_t or 0))
    if to_fill <= 0:
        return "FULL with this load"
    seconds = _hours_to(to_fill, rate)
    if seconds is None:
        return "%d/%d t" % (tonnes, capacity)
    return "in %s  %d/%d t" % (span_text(seconds), tonnes, capacity)


def load_text(last, average, count):
    """The timed loads: "24m  avg 26m (3)", "24m" for one, None for none."""
    if last is None:
        return None
    if count <= 1 or average is None:
        return span_text(last)
    return "%s  avg %s (%d)" % (span_text(last), span_text(average), count)
