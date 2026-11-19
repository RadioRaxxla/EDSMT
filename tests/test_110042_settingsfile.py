"""1.10042: Settings > Your data > Save settings to a file / Load settings
from a file. Secrets are left out on save and never taken on load; unknown
keys and values of the wrong kind are ignored; the rest goes through the
app's own settings load.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_settingsfile.py
"""
import faulthandler
import io
import json
import os
import sys
import tempfile

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-sf42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import settingsfile as SFL   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


defaults = {"overlay_opacity": "0.88", "overlay_show_status": True, "trash_days": 30,
            "inara_api_key": "", "staff_token": "", "theme": "Radio Raxxla"}
print("== save ==")
mine = dict(defaults, inara_api_key="KEYKEYKEY1", staff_token="STAFFSTAFF", overlay_show_status=False,
            discord_webhooks=[{"name": "m", "url": "https://discord.com/api/webhooks/1/abcdefghijklmnopqrstuvwx"}])
text = SFL.export_text(mine)
check("no key or token is in the file", "KEYKEYKEY1" not in text and "STAFFSTAFF" not in text
      and "abcdefghijklmnopqrstuvwx" not in text, text)
check("a plain setting is", '"overlay_show_status": false' in text)
print("== read ==")
accepted, ignored, problem = SFL.read_text(text, defaults)
check("the file reads back", not problem and accepted.get("overlay_show_status") is False, (accepted, problem))
check("the keys left out are not accepted", "inara_api_key" not in accepted and "staff_token" not in accepted)
hand = json.dumps({"settings": {"inara_api_key": "EVIL", "nonsense": 1, "trash_days": "lots",
                                "overlay_opacity": "0.5", "theme": 7}, "edsmt_settings_file": 1})
accepted, ignored, problem = SFL.read_text(hand, defaults)
check("a secret in the file is never taken", "inara_api_key" not in accepted and "inara_api_key" in ignored)
check("unknown keys are ignored", "nonsense" in ignored)
check("a value of the wrong kind is ignored", "trash_days" in ignored and "theme" in ignored, ignored)
check("a good value is kept", accepted == {"overlay_opacity": "0.5"}, accepted)
check("a number for a number, a bool is not a number",
      SFL.read_text('{"trash_days": true}', defaults)[0] == {} and SFL.read_text('{"trash_days": 9}', defaults)[0] == {"trash_days": 9})
check("a file that is not settings is a problem", SFL.read_text("nope", defaults)[2] != ""
      and SFL.read_text("[1]", defaults)[2] != "")
check("a byte-order mark does not matter", SFL.read_text("﻿" + text, defaults)[2] == "")
check("merge lays the accepted over what is in use",
      SFL.merge({"a": 1, "b": 2}, {"b": 3}) == {"a": 1, "b": 3})

print("== through the app ==")
import edsmt as E   # noqa: E402
os.makedirs(E.DATA_DIR, exist_ok=True)
now = dict(E.DEFAULT_SETTINGS, inara_api_key="MINE-KEEP-ME", overlay_show_status=True, overlay_opacity=0.9)
E.save_settings(now)
out = os.path.join(TMP, "saved.json")
E.save_settings_file(out, now)
body = read_back = open(out, encoding="utf-8").read()
check("the file the app writes has no key", "MINE-KEEP-ME" not in body)
edited = json.loads(body)
edited["settings"]["overlay_opacity"] = 0.4
edited["settings"]["inara_api_key"] = "THEIRS"
edited["settings"]["not_a_setting"] = 5
with open(out, "w", encoding="utf-8") as handle:
    json.dump(edited, handle)
fresh, taken, ignored = E.load_settings_file(out, dict(now))
check("the value loaded", fresh["overlay_opacity"] == 0.4 and taken >= 1, fresh.get("overlay_opacity"))
check("the key already here is untouched", fresh.get("inara_api_key") == "MINE-KEEP-ME", fresh.get("inara_api_key"))
check("the unknown key is not in the settings", "not_a_setting" not in fresh and "not_a_setting" in ignored)
check("what was there is kept beside it", any(n.startswith("settings.json.before-load-")
                                               for n in os.listdir(E.DATA_DIR)), os.listdir(E.DATA_DIR))
check("the always-on switches still hold", fresh.get("community_enabled", True) is True)
try:
    open(os.path.join(TMP, "bad.json"), "w").write("{not json")
    E.load_settings_file(os.path.join(TMP, "bad.json"), now)
    check("a bad file is refused", False)
except ValueError:
    check("a bad file is refused", True)
try:
    E.load_settings_file(os.path.join(TMP, "missing.json"), now)
    check("a missing file is refused", False)
except ValueError:
    check("a missing file is refused", True)

print("== wiring ==")
src = read("edsmt.py")
check("the two buttons are in Your data", "Save settings to a file" in src and "Load settings from a file" in src
      and "command=self.save_settings_now" in src and "command=self.load_settings_now" in src)
check("settingsfile is in both build specs", all('"settingsfile"' in read("build", s)
                                                  for s in ("EDSMT.spec", "EDSMT-onefile.spec")))
check("the guide says it", "save settings to a file" in read("docs", "GUIDE.md").lower())
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
