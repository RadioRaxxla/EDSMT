"""When the new Basic lines are said (1.2).

Seventeen lines approved 19 Nov 2026, each said by every voice:

  value_top, value_best   a deposit whose commodity is one of the five
                          best-paying on the prices known (the best of all
                          is value_best), when you mark it or drive onto it
  rich_patch              a deposit marked in the top patch of its location,
                          three or more deposits close together
  sell_here               docked where the cargo aboard sells best
  hold_full               the Rhino at 72 t, or the ship's hold full
  nearly_out, plenty_left driving onto a deposit with little, or most, of
                          what it holds left
  due_check               one of yours on this body is due a check
  guide_far               Guide me there set to a deposit on another body
  landed_marked           touchdown makes waypoint 1
  pin_skipped             Skip this pin
  import_done             an import finishes
  ribbon_earned           the map gives you a new ribbon step
  live_on, live_off       the Twitch live-status switch
  rhino_full_soon         the Rhino five minutes from full
  ship_full_soon          the ship one Rhino load from full

The rules are here; the app says the line. Pure: no window, no sound, no
network.
"""
import shiphold as SH
import survey as SV

LINE_IDS = ("value_top", "value_best", "rich_patch", "sell_here", "hold_full", "nearly_out",
            "plenty_left", "due_check", "guide_far", "landed_marked", "pin_skipped", "import_done",
            "ribbon_earned", "live_on", "live_off", "rhino_full_soon", "ship_full_soon")
TOP = 5
# Left of what a deposit like it holds: at or under this is nearly out, at
# or over PLENTY is plenty left.
NEARLY = 0.25
PLENTY = 0.75
SOON_S = 5 * 60.0
RICH_AT_LEAST = 3
# How near a deposit due a check has to be, on your body.
DUE_WITHIN_M = 2000.0


def _price(name, price_of):
    try:
        got = price_of(name)
    except Exception:
        return 0.0
    if isinstance(got, (tuple, list)):
        got = got[0] if got else 0
    try:
        value = float(got or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 else 0.0


def top_five(price_of, names):
    """The five best-paying commodities of `names`, best first, by the
    prices `price_of` knows. One with no price is not in it."""
    priced = [(_price(name, price_of), name) for name in names or ()]
    priced = [(value, name) for value, name in priced if value > 0]
    priced.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _value, name in priced[:TOP]]


def value_line(commodity, price_of, names):
    """"value_best" for the best-paying of `names`, "value_top" for one of
    the top five, else None."""
    wanted = SV.fold(SV.canonical(commodity) or commodity)
    if not wanted:
        return None
    best = top_five(price_of, names)
    folded = [SV.fold(SV.canonical(name) or name) for name in best]
    if wanted not in folded:
        return None
    return "value_best" if folded.index(wanted) == 0 else "value_top"


def left_line(left, holds):
    """"nearly_out" or "plenty_left" from sitetree.left() and holds() - each
    (low, high, how many, where from) - or None."""
    if not left or not holds:
        return None
    try:
        middle_left = (float(left[0]) + float(left[1])) / 2.0
        middle_full = (float(holds[0]) + float(holds[1])) / 2.0
    except (TypeError, ValueError, IndexError):
        return None
    if middle_full <= 0:
        return None
    share = middle_left / middle_full
    if share <= NEARLY:
        return "nearly_out"
    if share >= PLENTY:
        return "plenty_left"
    return None


class Once:
    """Each line once for each thing it is about, until it is forgotten."""

    def __init__(self):
        self._said = set()

    def first(self, kind, key):
        mark = (str(kind), str(key))
        if mark in self._said:
            return False
        self._said.add(mark)
        return True

    def forget(self, kind, key):
        self._said.discard((str(kind), str(key)))

    def forget_kind(self, kind):
        self._said = {mark for mark in self._said if mark[0] != str(kind)}


def _seconds(tonnes, rate):
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return None
    return tonnes / rate * 3600.0 if rate > 0 else None


def rhino_soon(rhino_t, rate, full=SH.RHINO_HOLD_T):
    """True when the Rhino is not full and will be inside five minutes."""
    if rhino_t is None:
        return False
    held = int(rhino_t)
    if held >= full:
        return False
    seconds = _seconds(full - held, rate)
    return seconds is not None and seconds <= SOON_S


def _ship_free(card, rhino_t):
    if not card or not card.get("known") or not card.get("capacity"):
        return None
    return int(card["capacity"]) - int(card.get("tonnes") or 0) - max(0, int(rhino_t or 0))


def ship_soon(card, rhino_t):
    """True when the ship is not full and one Rhino load would fill it."""
    if not card or not card.get("known") or not card.get("capacity"):
        return False
    if int(card.get("tonnes") or 0) >= int(card["capacity"]):
        return False
    free = _ship_free(card, rhino_t)
    return free is not None and 0 < free <= SH.RHINO_HOLD_T


def hold_full(card, rhino_t):
    """True when the Rhino holds 72 t or the ship's hold is full."""
    if rhino_t is not None and int(rhino_t) >= SH.RHINO_HOLD_T:
        return True
    return bool(card and card.get("known") and card.get("capacity")
                and int(card.get("tonnes") or 0) >= int(card["capacity"]))


def rich_patch(deposit_id, rows):
    """True when the deposit is in its location's top patch and the patch
    has three or more deposits. `rows` as sitetree.deposits() gives them."""
    if not deposit_id or not rows:
        return False
    top = [row for row in rows if row.get("patch") == 1]
    return len(top) >= RICH_AT_LEAST and any(str(row.get("id")) == str(deposit_id) for row in top)


def sells_best(found, best_of):
    """True when the commodity that makes most of a sale here (the first of
    presale.quote()'s parts) sells here for at least the best price known
    for it. `best_of` gives credits a tonne, as value_line's price_of does."""
    parts = (found or {}).get("parts") if isinstance(found, dict) else None
    if not parts:
        return False
    top = parts[0] or {}
    try:
        here = float(top.get("sell") or 0)
    except (TypeError, ValueError):
        return False
    best = _price(top.get("commodity"), best_of)
    return here > 0 and best > 0 and here >= best


def due_near(rows, within=DUE_WITHIN_M, skip=None):
    """The id of the nearest deposit due a check on the body you are on,
    within `within` metres and not `skip` (the one you are standing on), or
    None. `rows` as recheck.due_rows() gives them, nearest first."""
    for row in rows or ():
        if row.get("place") != 0:
            continue
        metres = row.get("metres")
        if metres is None or metres > within:
            continue
        ident = (row.get("deposit") or {}).get("id")
        if not ident or (skip is not None and str(ident) == str(skip)):
            continue
        return str(ident)
    return None


def live_change(before, now):
    """"live_on" or "live_off" when the live-status switch has just been
    turned; None when it has not, or on the first look (`before` None)."""
    if before is None or bool(before) == bool(now):
        return None
    return "live_on" if now else "live_off"


class FillCues:
    """hold_full, rhino_full_soon and ship_full_soon, each at most once a
    Rhino load. A load ends when what the Rhino holds goes down (unloaded
    into the ship)."""

    def __init__(self):
        self._last = None
        self._said = set()

    def step(self, rhino_t, card, rate, rhino_full_said=False):
        """The lines due now. `rhino_full_said`: something else already says
        the Rhino is full (Celestia's own reaction), so only the ship's full
        hold is said as hold_full."""
        if rhino_t is None:
            return []
        try:
            held = int(rhino_t)
        except (TypeError, ValueError):
            return []
        if self._last is not None and held < self._last:
            self._said = set()
        self._last = held
        due = []
        rhino_full = held >= SH.RHINO_HOLD_T
        ship_full = hold_full(card, None)
        if (ship_full or (rhino_full and not rhino_full_said)):
            due.append("hold_full")
        elif rhino_soon(held, rate):
            due.append("rhino_full_soon")
        if ship_soon(card, held):
            due.append("ship_full_soon")
        out = [line for line in due if line not in self._said]
        self._said.update(due)
        return out


def ribbon_count(answer):
    """The ribbon steps earned in all, from the map's ribbons answer, or None."""
    try:
        return int((answer or {}).get("earned"))
    except (TypeError, ValueError, AttributeError):
        return None


def ribbon_new(before, answer):
    """True when the answer has more ribbon steps than `before`. The first
    look (`before` None) only notes how many."""
    now = ribbon_count(answer)
    return before is not None and now is not None and now > int(before)
