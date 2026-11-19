"""1.10042: settings and finds backed up at every start, newest 30 kept; what
Settings > Your data says about them and the map pictures.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_backups.py
"""
import faulthandler
import io
import json
import os
import sys
import tempfile
import time
import zipfile

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-bk42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import startbackup as SBK    # noqa: E402
import folderstats as FS     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


def put(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


print("== the backup ==")
data = os.path.join(TMP, "data")
put(os.path.join(data, "surfaceminingmap.csv"), "a,b\n1,2\n")
put(os.path.join(data, "sessions.csv"), "s\n")
put(os.path.join(data, "finds.json"), json.dumps({"note": "key SECRETKEY123 here"}))
put(os.path.join(data, "settings.json"), '{"inara_api_key": "SECRETKEY123"}')
put(os.path.join(data, "settings.json.bak"), '{"inara_api_key": "SECRETKEY123"}')
put(os.path.join(data, "settings-history", "settings-20260101-000000.json"), "SECRETKEY123")
put(os.path.join(data, "coverage", "body1.json"), "{}")
put(os.path.join(data, "pictures", "a.png"), "png")
settings = {"inara_api_key": "SECRETKEY123", "community_token": "TOK-ABC-987",
            "portal_token": "PORTALTOK55", "staff_token": "STAFFTOK77",
            "discord_webhooks": [{"name": "m", "url": "https://discord.com/api/webhooks/123/abcdefghijklmnopqrstuvwx"}],
            "map_picture_auto": True}
dest = os.path.join(TMP, "backups")
when = time.mktime((2026, 11, 18, 10, 0, 0, 0, 0, -1))
path, wrote, problem = SBK.run(data, settings, place=type("P", (), {"folder": lambda s: dest})(), when=when)
check("a zip is written, with no problem", bool(path) and os.path.isfile(path) and not problem, problem)
check("named for the day and time", os.path.basename(path) == "EDSMT-start-20261118-100000.zip", path)
with zipfile.ZipFile(path) as z:
    names = z.namelist()
    blob = b"".join(z.read(n) for n in names).decode("utf-8", "replace")
check("settings, finds, sessions and the survey are in it",
      all(n in names for n in ("settings.json", "surfaceminingmap.csv", "sessions.csv",
                               "finds.json", "coverage/body1.json")), names)
check("the old settings copies and pictures are not", not any(
    n.startswith(("settings-history", "pictures")) or n == "settings.json.bak" for n in names), names)
for secret in ("SECRETKEY123", "TOK-ABC-987", "PORTALTOK55", "STAFFTOK77", "abcdefghijklmnopqrstuvwx"):
    check("no %s in the zip" % secret[:8], secret not in blob)
check("a switch survives in the settings", json.loads(zipfile.ZipFile(path).read("settings.json"))["map_picture_auto"] is True)

print("== keep 30 ==")
old = os.path.join(dest, "stray.zip")
put(old)
for i in range(35):
    put(os.path.join(dest, "EDSMT-start-2026%02d%02d-000000.zip" % (1 + i // 28, 1 + i % 28)))
SBK.tidy(dest)
mine = SBK.list_backups(dest)
check("30 left", len(mine) == 30, len(mine))
check("the newest are the ones kept", "EDSMT-start-20260207-000000.zip" in mine
      and "EDSMT-start-20260101-000000.zip" not in mine)
check("a file that is not one of these is left alone", os.path.exists(old))
path2, _, _ = SBK.run(data, settings, place=type("P", (), {"folder": lambda s: dest})(), when=when + 60)
check("a new backup keeps the total at 30", len(SBK.list_backups(dest)) == 30)

print("== never raises ==")
blocker = os.path.join(TMP, "afile")
put(blocker)
bad = SBK.run(data, settings, place=type("P", (), {"folder": lambda s: os.path.join(blocker, "x")})())
check("an unwritable place is a problem string, not a crash", bad[0] == "" and bad[2] != "", bad)
check("a missing data folder still backs up the settings",
      SBK.run(os.path.join(TMP, "nodata"), settings,
              place=type("P", (), {"folder": lambda s: dest})(), when=when + 120)[1] == 1)
check("the default place is under EDTools/Backup/RadioRaxxla/EDSMT",
      SBK.Place().folder().replace("\\", "/").endswith("EDTools/Backup/RadioRaxxla/EDSMT"))

print("== folder facts (map pictures) ==")
pics = os.path.join(TMP, "pics")
put(os.path.join(pics, "a.png"), "x" * 2048)
put(os.path.join(pics, "b.png"), "x" * 1024)
put(os.path.join(pics, "note.txt"), "x" * 99)
n, size = FS.count_and_size(pics, (".png",))
check("pictures counted, other files not", n == 2 and size == 3072, (n, size))
check("a missing folder is none", FS.count_and_size(os.path.join(TMP, "no"), (".png",)) == (0, 0))
check("sizes read plainly", FS.size_words(0) == "0 KB" and FS.size_words(2048) == "2 KB"
      and FS.size_words(5 * 1024 * 1024) == "5.0 MB" and FS.size_words(1500) == "1.5 KB", 
      [FS.size_words(x) for x in (0, 2048, 5 * 1024 * 1024, 1500)])
check("the line says count and size", FS.pictures_line(2, 3072) == "2 saved map pictures, 3 KB"
      and FS.pictures_line(1, 1024) == "1 saved map picture, 1 KB"
      and FS.pictures_line(0, 0) == "No saved map pictures yet", FS.pictures_line(2, 3072))

print("== wiring ==")
src = read("edsmt.py")
check("the app runs the start backup off the window's thread", "STB.run(" in src and "threading.Thread" in src
      and "start_backup" in src)
check("Settings > Your data says where, with an Open folder button",
      "Open backup folder" in src and "backup_place" in src)
check("Settings > Your data shows the map picture count", "FS.pictures_line" in src)
check("both new modules are in both build specs", all(
    m in read("build", spec) for spec in ("EDSMT.spec", "EDSMT-onefile.spec")
    for m in ('"startbackup"', '"folderstats"')))
check("the guide mentions the start backup", "every start" in read("docs", "GUIDE.md").lower())

print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
