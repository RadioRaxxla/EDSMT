"""Keeping the map right: asking, remembering, and listing what is due a
check (1.10042).

  * driving onto a deposit you have marked asks once "Still there? UPDATE or
    DEPOSIT DEPLETED"; leaving without answering is one line, and the deposit goes
    on a "visited, not updated" list that waits for the next start;
  * Find's "Due a check": deposits nobody has confirmed for a while, and
    worked-out ones that may be back, nearest first.

From 1.2 the same for other commanders' finds the app has fetched: asked
once when you drive onto one with none of yours under you, your answer going
to the community map, and listed in Due a check saying whose each is.

Pure: it is handed the deposits, the clock and where you are. It opens no
window and asks nobody for anything.
"""
import datetime as _dt
import time as _time

import regrowth as RG
import survey as SV

ASK = "Still there? UPDATE or DEPOSIT DEPLETED"
# Not asked again for a deposit you answered this recently (driving back and
# forth across one).
RECENT_S = 600.0
# A week: the same time the community map counts a check on an old site by.
CONFIRM_DAYS = 7
KEY = "visited_not_updated"
# Another commander's find somebody reported this recently is not asked about.
THEIRS_FRESH_S = 86400.0


def left_line(commodity):
    """The one line when you drive off without answering."""
    return ("Left the %s deposit without UPDATE or DEPOSIT DEPLETED - it is on your "
            "list to check at the next start." % (commodity or "deposit"))


def _seconds(text):
    """A stored date or the map's ISO stamp (with +00:00) as seconds, or None."""
    text = str(text or "").strip()
    if not text:
        return None
    try:
        when = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return RG.when_of(text)
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.timezone.utc)
    return when.timestamp()


def theirs_line(row):
    """The words when you drive onto another commander's find."""
    return ("%s's %s deposit: still there? UPDATE or DEPOSIT DEPLETED - your answer goes on the "
            "community map for everyone." % ((row or {}).get("cmdr") or "Another commander",
                                             (row or {}).get("commodity") or "unnamed"))


def seen_lately(row, now):
    """True when anybody reported another commander's find within THEIRS_FRESH_S."""
    at = _seconds((row or {}).get("when"))
    return bool(at) and 0 <= now - at < THEIRS_FRESH_S


def shared_checkable(row, now=None):
    """Another commander's find, as the app files it from the map, in the
    shape due_rows() reads: when anybody last reported it as "recorded", and
    for a worked-out one when it was worked out as "depleted_at". A copy;
    None for anything that is not a shared find."""
    if not isinstance(row, dict) or not row.get("shared"):
        return None
    now = _time.time() if now is None else now
    out = dict(row)
    seen = _seconds(row.get("when"))
    out["recorded"] = RG.stamp(seen) if seen else ""
    for key in ("checked_at", "mined_at", "depleted_at"):
        out.pop(key, None)
    days = row.get("worked_out_days")
    if RG.depleted(row) and days not in (None, ""):
        try:
            out["depleted_at"] = RG.stamp(now - float(days) * RG.DAY)
        except (TypeError, ValueError):
            pass
    return out


def due_order(rows):
    """Due rows, from due_rows() or more than one call of it, nearest first."""
    return sorted(rows, key=lambda r: (r["place"], r["metres"] is None, r["metres"] or 0.0,
                                       -r["days"], str(r["deposit"].get("commodity") or "").lower()))


def recently_checked(deposit, now):
    """True when you answered for this deposit within RECENT_S."""
    at = RG.when_of((deposit or {}).get("checked_at"))
    return bool(at) and 0 <= now - at < RECENT_S


def checked_changes(now=None):
    """What a check writes onto a deposit: when you last confirmed it."""
    import time
    return {"checked_at": RG.stamp(time.time() if now is None else now)}


class Visits:
    """The deposits driven onto and not answered, oldest first. Kept in the
    settings it is given (a dict), so they are there at the next start."""

    def __init__(self, settings):
        self.settings = settings if isinstance(settings, dict) else {}

    def _book(self):
        book = self.settings.get(KEY)
        if not isinstance(book, dict):
            book = self.settings[KEY] = {}
        return book

    def ids(self):
        book = self._book()
        return sorted(book, key=lambda key: (str(book[key]), key))

    def add(self, deposit_id, now):
        """Note a visit. A deposit already on the list keeps its first one."""
        if deposit_id:
            self._book().setdefault(str(deposit_id), RG.stamp(now))

    def clear(self, deposit_id):
        self._book().pop(str(deposit_id), None)

    def pending(self, deposits):
        """The deposits still in the store that are on the list, oldest
        visit first. One that has gone from the store is dropped."""
        have = {str(row.get("id")): row for row in deposits or []}
        book = self._book()
        for key in [k for k in book if k not in have]:
            del book[key]
        return [have[key] for key in self.ids()]


def last_touch(deposit):
    """When anybody last confirmed a deposit, as seconds: your last check, the
    last tonne refined at it, or when it was marked."""
    best = 0.0
    for key in ("checked_at", "mined_at", "recorded"):
        at = RG.when_of((deposit or {}).get(key))
        if at and at > best:
            best = at
    return best or None


def due_rows(deposits, now, regrow_days=None, here=None, days=CONFIRM_DAYS):
    """The deposits due a check, nearest first, each as {"deposit", "kind",
    "words", "metres", "days"}. `kind` is "back" for a worked-out deposit that
    may be back, "due" for one nobody has confirmed for `days`. A worked-out
    deposit with nothing measured is not due until RG.HOLD_DAYS. `here` is
    where you are: {"system", "body", "lat", "lon", "radius_m"}. `regrow_days`
    is the measured days, or a function of the commodity that gives them."""
    out = []
    for deposit in deposits or []:
        if RG.depleted(deposit):
            measured = regrow_days(deposit.get("commodity")) if callable(regrow_days) \
                else regrow_days
            info = RG.standing(deposit, now, measured)
            if not info["due"]:
                continue
            kind, words, age = "back" if info["state"] == "back" else "due", info["text"], \
                info.get("age_days")
        else:
            touched = last_touch(deposit)
            if touched is None or now - touched < days * RG.DAY:
                continue
            age = int((now - touched) // RG.DAY)
            kind, words = "due", "not checked for %d day%s" % (age, "" if age == 1 else "s")
        out.append({"deposit": deposit, "kind": kind, "words": words,
                    "metres": _metres(deposit, here), "days": age or 0,
                    "place": _place(deposit, here)})
    return due_order(out)


def _place(deposit, here):
    """0 on the body you are on, 1 in the system, 2 elsewhere."""
    if not here:
        return 2
    if SV.fold(deposit.get("system")) != SV.fold(here.get("system")):
        return 2
    return 0 if SV.fold(deposit.get("body")) == SV.fold(here.get("body")) else 1


def _metres(deposit, here):
    if not here or _place(deposit, here) != 0:
        return None
    try:
        return SV.surface_range_m(float(here["lat"]), float(here["lon"]),
                                  float(deposit["lat"]), float(deposit["lon"]),
                                  float(here.get("radius_m") or 0) or 1e6)
    except (KeyError, TypeError, ValueError):
        return None


def away_metres(deposit, here):
    """How far a deposit is from where you are, in metres, or None when you
    are not on its body or either position is not known. `here` is
    {"system", "body", "lat", "lon", "radius_m"}."""
    return _metres(deposit, here)


def visit_lines(deposit, centre_words="", away=None, metres_text=str):
    """The three lines that say WHICH deposit a row of the visited list is.
    Two deposits of one commodity in one location have the same name, so a
    row carries what is recorded for the deposit and where it lies:

        Iridium - 4 rigs, Amount Medium, Density High
        Signal 21: 1.24 km NE 045 from the centre, 340 m from you
        Col 285 Sector KB-W c2-14 BC 2 at 14.0130, -79.8287

    `centre_words` is its place from the location's centre as the window
    writes it ("" or "-" when not known), `away` how far it is from you now
    in metres (None when not known), `metres_text` the window's own way of
    writing a distance. Nothing is said that is not known."""
    deposit = deposit or {}
    recorded = []
    try:
        rigs = int(float(deposit.get("rigs")))
    except (TypeError, ValueError):
        rigs = 0
    if rigs > 0:
        recorded.append("%d rig%s" % (rigs, "" if rigs == 1 else "s"))
    for label, key in (("Amount", "amount"), ("Density", "density")):
        value = str(deposit.get(key) or "").strip()
        if value:
            recorded.append("%s %s" % (label, value))
    title = str(deposit.get("commodity") or "").strip() or "Deposit"
    if recorded:
        title += " - " + ", ".join(recorded)
    where = []
    centre_words = str(centre_words or "").strip()
    if centre_words == "at the centre":
        where.append(centre_words)
    elif centre_words and centre_words != "-":
        where.append(centre_words + " from the centre")
    if away is not None:
        where.append("%s from you" % metres_text(away))
    signal = "Signal %s" % (str(deposit.get("location") or "").strip() or "-")
    if where:
        signal += ": " + ", ".join(where)
    place = str(deposit.get("body") or "").strip() or str(deposit.get("system") or "").strip()
    try:
        spot = "%.4f, %.4f" % (float(deposit["lat"]), float(deposit["lon"]))
    except (KeyError, TypeError, ValueError):
        spot = ""
    return [title, signal, (place + " at " + spot) if place and spot else (place or spot)]


# -- the how-to: the same words in the guide, in Help and in the welcome ----

HOWTO_TITLE = "Keeping the map right"
HOWTO_WORDS = (
    "The map is only as good as the last person to check it. When you drive "
    "the SRV onto a deposit you have marked, EDSMT asks once, on the overlay, "
    "and aloud with Windows voice picked: Still there? UPDATE or DEPOSIT DEPLETED. UPDATE puts the Amount, "
    "Density or rigs you can see now onto it. DEPOSIT DEPLETED marks it worked out "
    "and sends the tonnes it gave, so everyone can see what a deposit like it "
    "holds."
    "\n\n"
    "Other commanders' finds too. Drive onto another commander's find with "
    "none of yours under you and EDSMT asks the same, saying whose it is. "
    "UPDATE says it is still there and DEPOSIT DEPLETED that it is worked out; "
    "either goes on the community map for everyone. It is not asked about a "
    "find somebody reported today, nor one already worked out."
    "\n\n"
    "Drive off without answering and EDSMT says so in one line and keeps the "
    "deposit on a short list (your own deposits only). At the next start a small window offers Still "
    "there, Deposit depleted or Skip for each one, and Show opens the deposit in "
    "My sites so you can tell which one it is. It never holds the start up, and "
    "it is not there when the list is empty."
    "\n\n"
    "A worked-out mark stays until you take it off, or until the first tonne "
    "is refined there. Once enough commanders have reported how long deposits "
    "take to come back, a worked-out deposit says when it is expected back, "
    "and after that it reads \"may be back - needs a check\". Find has a Due a "
    "check search: your deposits nobody has confirmed for a while, nearest "
    "first, and other commanders' finds on the bodies you have been to, each "
    "saying whose it is."
    "\n\n"
    "Checks count on the leaderboard: 2 points for an update, 3 for mined "
    "out, 5 for finding a worked-out deposit grown back. The Site checker "
    "ribbons count them too.")
