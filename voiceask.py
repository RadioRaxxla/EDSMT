"""The question asked before any voice is heard (1.10042).

"Do you want EDSMT to speak?" - Yes, No or Choose a voice. It is put on a
first start and once on the first start after updating to a version that
has it - the starts where the welcome is due - and never again: the answer
is kept in the settings as voice_asked. Plain logic only; the window is
thin wiring in edsmt.py.
"""

import welcome as WL

QUESTION = "Do you want EDSMT to speak?"
NOTE = ("EDSMT can say what it has just done - signal logged, rig two down - "
        "so you need not look away from the game. You can change this at "
        "any time in Settings, on the Audio tab.")
ANSWERS = (("yes", "Yes"), ("no", "No"), ("choose", "Choose a voice"))


def ask_due(settings, version):
    """True when the question is to be put at this start: it has never been
    answered, and this is a start of a first run or of a new version (the
    welcome, or the sharing question, is due)."""
    data = settings if isinstance(settings, dict) else {}
    if data.get("voice_asked"):
        return False
    return (not data.get("asked_to_share")) or WL.welcome_due(data, version)


def answer(key):
    """The settings an answer sets. An answer that is not one of the three -
    the window closed - leaves the voice as it was and is still an answer."""
    key = str(key or "").strip().lower()
    if key in ("yes", "choose"):
        return {"voice_mode": True, "voice_asked": True}
    if key == "no":
        return {"voice_mode": False, "voice_asked": True}
    return {"voice_asked": True}


def opens_settings(key):
    """Only Choose a voice goes on to the Audio settings."""
    return str(key or "").strip().lower() == "choose"
