"""Your own good and bad marks on the places you have logged (1.10042).

A mark of your own on any location you have logged - up for one worth
coming back to, down for one that is not - that lists your sites up first
and down last, and colours them. Press the lit mark again and it comes off.

These are kept on this PC only, in one JSON file beside your records, and
never sent anywhere: they are not the good and bad marks of the community
map (sitemarks.py), which count towards how far everyone trusts a site.
A mark brought in by an import is kept the same way.

Pure logic and one file; no toolkit, no network.
"""
import json
import os
import time

UP, DOWN = "up", "down"
MARKS = (UP, DOWN)
FILE_NAME = "own_marks.json"
# How each mark is written on its button.
LABELS = {UP: "▲ up", DOWN: "▼ down"}


def _tidy(text):
    return " ".join(str(text or "").split())


def key_of(system, body, location=""):
    """One location, whatever the case or spacing it was written with."""
    return "|".join((_tidy(system).lower(), _tidy(body).lower(), _tidy(location).lower()))


class OwnMarks:
    """The marks, by location."""

    def __init__(self, path=None):
        self.path = path
        self.marks = {}

    def load(self):
        """Read the file. True when it read; a missing or damaged file is an
        empty book."""
        if not self.path or not os.path.exists(self.path):
            return False
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            self.marks = {key: dict(entry) for key, entry in (data.get("marks") or {}).items()
                          if isinstance(entry, dict) and entry.get("mark") in MARKS}
        except (OSError, ValueError, TypeError, AttributeError):
            self.marks = {}
            return False
        return True

    def save(self):
        """Write the file, through a temporary one. False when it could not."""
        if not self.path:
            return False
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            spare = self.path + ".tmp"
            with open(spare, "w", encoding="utf-8") as handle:
                json.dump({"marks": self.marks}, handle, indent=1)
            os.replace(spare, self.path)
            return True
        except OSError:
            return False

    def mine(self, system, body, location=""):
        """"up", "down", or "" for a location with no mark of yours."""
        entry = self.marks.get(key_of(system, body, location))
        return entry["mark"] if entry else ""

    def set(self, system, body, location, mark, now=None):
        """Put a mark on a location, or take it off with "". False when
        nothing changed, or for anything that is not a mark."""
        if mark not in MARKS + ("",) or not _tidy(system) or not _tidy(body):
            return False
        key = key_of(system, body, location)
        if mark == "":
            return self.marks.pop(key, None) is not None
        if self.marks.get(key, {}).get("mark") == mark:
            return False
        self.marks[key] = {"system": _tidy(system), "body": _tidy(body),
                           "location": _tidy(location), "mark": mark,
                           "at": float(time.time() if now is None else now)}
        return True

    def press(self, system, body, location, mark, now=None):
        """A mark's button pressed: it goes on, or - already lit - comes off.
        Returns the mark the location has now ("" for none)."""
        if self.mine(system, body, location) == mark:
            self.set(system, body, location, "")
        else:
            self.set(system, body, location, mark, now)
        return self.mine(system, body, location)


def rank(mark):
    """Where a mark puts a location: up first, none, down last."""
    return {UP: 0, DOWN: 2}.get(mark, 1)


def buttons(book, system, body, location=""):
    """[(text, mark, lit)] for a location's two marks, yours lit."""
    mine = book.mine(system, body, location) if book is not None else ""
    return [(LABELS[mark], mark, mine == mark) for mark in MARKS]
