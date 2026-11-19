"""Live status for the Radio Raxxla Twitch bot (1.10042).

A commander who switches it on is answered for in their Twitch chat:
!system, !ship, !rank, !session and !edsmt. About every half minute the app
tells the community map where they are - the system and body, never a
position, and never while streamer mode is hiding them - what they fly,
their ranks and how the session is going. Switched off, it is taken down.

This module is the plain part: the ranks' names, when to send, and the
answer put together from what the app already has. Sending it is the
community client's. Nothing here needs a window.
"""

TAG = "now"
EVERY_S = 30.0

_TOP = ("Elite", "Elite I", "Elite II", "Elite III", "Elite IV", "Elite V")
# The answer's name for each rank, the journal's name for it, and the ladder
# from 0 up as the game names it.
RANKS = (
    ("combat", "Combat", ("Harmless", "Mostly Harmless", "Novice", "Competent", "Expert",
                          "Master", "Dangerous", "Deadly") + _TOP),
    ("trade", "Trade", ("Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant",
                        "Broker", "Entrepreneur", "Tycoon") + _TOP),
    ("exploration", "Explore", ("Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer",
                                "Pathfinder", "Ranger", "Pioneer") + _TOP),
    ("mercenary", "Soldier", ("Defenceless", "Mostly Defenceless", "Rookie", "Soldier",
                              "Gunslinger", "Warrior", "Gladiator", "Deadeye") + _TOP),
    ("exobiologist", "Exobiologist", ("Directionless", "Mostly Directionless", "Compiler",
                                      "Collector", "Cataloguer", "Taxonomist", "Ecologist",
                                      "Geneticist") + _TOP),
    ("cqc", "CQC", ("Helpless", "Mostly Helpless", "Amateur", "Semi Professional",
                    "Professional", "Champion", "Hero", "Legend") + _TOP),
)


def rank_names(numbers):
    """{"combat": "Elite", ...} from the journal's Rank numbers. None for a
    rank the journal has not given, or a number off the ladder."""
    numbers = numbers if isinstance(numbers, dict) else {}
    out = {}
    for key, journal_key, ladder in RANKS:
        value = numbers.get(journal_key)
        ok = isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(ladder)
        out[key] = ladder[value] if ok else None
    return out


def step(on, was_on, last_sent, now, every=EVERY_S):
    """What to do now: "send", "clear" (switched off since the last send:
    take it down, once) or None."""
    if on:
        return "send" if (not was_on or now - (last_sent or 0.0) >= every) else None
    return "clear" if was_on else None


def _whole(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def build(stream, ship_type="", ship_name="", ranks=None, version=""):
    """The status to send, from the stream card's own state (what the OBS
    page shows, so streamer mode has already hidden what it hides), the ship
    and the ranks. Never a position. Never raises."""
    stream = stream if isinstance(stream, dict) else {}
    session = stream.get("session") if isinstance(stream.get("session"), dict) else {}
    ranks = ranks if isinstance(ranks, dict) else {}
    return {
        "system": str(stream.get("system") or "") or None,
        "body": str(stream.get("body") or "") or None,
        "ship": {"type": str(ship_type or "") or None, "name": str(ship_name or "") or None},
        "ranks": {key: ranks.get(key) or None for key, _journal, _ladder in RANKS},
        "session": {"running": bool(session.get("running")),
                    "doing": str(stream.get("doing") or "") or None,
                    "tonnes": _whole(stream.get("tonnes_total")),
                    "credits_per_hour": _whole(stream.get("cr_hr")),
                    "minutes": _whole(session.get("seconds")) // 60,
                    "rigs_out": _whole(stream.get("rigs_down"))},
        "edsmt": {"version": str(version or "") or None},
    }
