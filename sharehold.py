"""Finds waiting for the commander's name (1.10041).

Every find is shared with the CMDR name on it, and the name only ever comes
from the journal. A find marked before the game has said who is playing -
EDSMT opened first, or an import run with the game closed - is held here
and goes up by itself once the name is known. Held on disk, so closing
EDSMT in between loses nothing.

Plain logic and one small file in the data folder: no window, no network.
"""
import json
import os

FILE_NAME = "held-finds.json"
# The most finds held. Past this the oldest go: a hold this long means the
# journal is not being read at all, which the app says in its own words.
MOST = 500


def _key(row):
    """What makes two rows the same find: where it is and what it is."""
    return (str(row.get("system", "")).strip().lower(),
            str(row.get("planet", "")).strip().lower(),
            str(row.get("spot", "")).strip().lower(),
            str(row.get("type", "")).strip().lower(),
            row.get("lat"), row.get("lon"))


class Hold:
    """The finds held for one data folder."""

    def __init__(self, folder):
        self.path = os.path.join(folder, FILE_NAME) if folder else ""
        self.rows = self._load()

    def _load(self):
        if not self.path:
            return []
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)][-MOST:]

    def _save(self):
        if not self.path:
            return
        try:
            if not self.rows:
                if os.path.exists(self.path):
                    os.remove(self.path)
                return
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(self.rows, handle)
            os.replace(temp, self.path)
        except OSError:
            pass            # held for this run; the next change tries again

    @property
    def count(self):
        return len(self.rows)

    def add(self, rows):
        """Hold these finds. How many were new."""
        have = {_key(row) for row in self.rows}
        added = 0
        for row in rows or []:
            if not isinstance(row, dict) or _key(row) in have:
                continue
            have.add(_key(row))
            self.rows.append(dict(row))
            added += 1
        if len(self.rows) > MOST:
            del self.rows[:-MOST]
        if added:
            self._save()
        return added

    def take(self):
        """Every held find, oldest first; the hold is empty afterwards."""
        rows, self.rows = self.rows, []
        self._save()
        return rows
