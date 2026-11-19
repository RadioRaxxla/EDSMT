"""A backup at every start (1.10042): one dated zip, the newest 30 kept.

The settings and the commander's own data - finds, sites, sessions - go in
one zip in a folder of their own (C:\\EDTools\\Backup\\RadioRaxxla\\EDSMT, or
~/EDTools/Backup/RadioRaxxla/EDSMT on Linux). Keys and tokens are left out:
the settings in the zip are the ones the support bundle would carry, and
the dated copies of the settings are not included, because they hold them
unchanged. Only zips this wrote are ever removed.

Pure file work, no window. The app runs it on a thread of its own after the
window is up and says one status line with the result.
"""
import os
import time
import zipfile

import supportbundle as SB

KEEP = 30
PREFIX = "EDSMT-start-"
KINDS = (".csv", ".json", ".log")
# Folders inside the data folder that hold data, not settings.
FOLDERS = ("coverage",)
SETTINGS_NAME = "settings.json"


class Place:
    """Where the backups go. The tests hand the app one of their own."""

    def folder(self):
        if os.name == "nt":
            return os.path.join("C:\\", "EDTools", "Backup", "RadioRaxxla", "EDSMT")
        return os.path.join(os.path.expanduser("~"), "EDTools", "Backup",
                            "RadioRaxxla", "EDSMT")


def _is_settings_file(name):
    low = name.lower()
    return low.startswith("settings") and ".json" in low


def zip_name(when=None):
    return "%s%s.zip" % (PREFIX, time.strftime("%Y%m%d-%H%M%S",
                                               time.localtime(when or time.time())))


def tidy(folder, keep=KEEP):
    """Keep the newest `keep` start backups; returns how many were removed.
    Names sort by their date, so that is the order. Nothing else is touched."""
    try:
        mine = sorted(n for n in os.listdir(folder)
                      if n.startswith(PREFIX) and n.endswith(".zip"))
    except OSError:
        return 0
    gone = 0
    for name in mine[:max(0, len(mine) - int(keep))]:
        try:
            os.remove(os.path.join(folder, name))
            gone += 1
        except OSError:
            pass
    return gone


def list_backups(folder):
    """The start backups in `folder`, newest first, as file names."""
    try:
        return sorted((n for n in os.listdir(folder)
                       if n.startswith(PREFIX) and n.endswith(".zip")), reverse=True)
    except OSError:
        return []


def make(data_dir, settings, folder, when=None, keep=KEEP):
    """Write one backup into `folder`. Returns (path, files written).

    Raises OSError if the zip cannot be written. Settings go in with every
    secret removed; the data files go in as they are, except that a json
    file has any secret value scrubbed out of it."""
    os.makedirs(folder, exist_ok=True)
    when = when or time.time()
    path = os.path.join(folder, zip_name(when))
    temp = path + ".tmp"
    secrets = SB.secret_values(settings or {})
    import json
    wrote = 0
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(SETTINGS_NAME, json.dumps(
            SB.clean_settings(settings or {}), indent=2, ensure_ascii=False))
        wrote += 1
        for base, prefix in [(data_dir, "")] + [
                (os.path.join(data_dir, sub), sub + "/") for sub in FOLDERS]:
            try:
                names = sorted(os.listdir(base))
            except OSError:
                continue
            for name in names:
                full = os.path.join(base, name)
                if (not os.path.isfile(full) or not name.endswith(KINDS)
                        or _is_settings_file(name)):
                    continue
                if name.endswith(".json"):
                    with open(full, "r", encoding="utf-8", errors="replace") as handle:
                        bundle.writestr(prefix + name, SB.scrub(handle.read(), secrets))
                else:
                    bundle.write(full, prefix + name)
                wrote += 1
    os.replace(temp, path)
    tidy(folder, keep)
    return path, wrote


def run(data_dir, settings, place=None, when=None):
    """make() for the app: never raises. Returns (path, files, problem)."""
    try:
        folder = (place or Place()).folder()
        path, wrote = make(data_dir, dict(settings or {}), folder, when)
        return path, wrote, ""
    except (OSError, zipfile.BadZipFile, ValueError) as problem:
        return "", 0, str(problem)
