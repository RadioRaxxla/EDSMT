"""1.2: the voices, sounds and artwork are not free to use elsewhere.

His words, 19 Nov: "we must put some where that the voicelines and files can
not be used else where to protect our product". The program code stays
GPL-3.0-only; ASSETS-LICENCE.txt says the recordings, sounds, names and
logos are Radio Raxxla's, all rights reserved, for use within EDSMT only. It
ships with every build, and the README, the About text and the voice folder
point to it.

    python3 tests/test_12_assets.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    return open(os.path.join(REPO, *parts), encoding="utf-8").read()


NAME = "ASSETS-LICENCE.txt"
path = os.path.join(REPO, NAME)
check("the notice is there", os.path.isfile(path))
text = read(NAME) if os.path.isfile(path) else ""
flat = " ".join(text.split())
check("all rights reserved, Radio Raxxla's", "All rights reserved" in flat and "Radio Raxxla" in flat)
check("it names the voice recordings, the sounds and the logos",
      all(word in flat for word in ("voice recordings", "voice\\", "sounds\\", "edsmt-badge")))
check("within EDSMT only, and not in any other program, pack, video or voice",
      "only for use within EDSMT" in flat and "any other program" in flat and "clone" in flat)
check("the code stays GPL-3.0-only", "GPL-3.0-only" in flat)
check("a copy of the code leaves them out", "fork" in flat and "leave them out" in flat)
check("the fonts and Frontier's pictures are not claimed",
      "fonts\\" in flat and "Frontier Developments" in flat and "rhino-about.png" in flat)
check("plain words, no word the public must not see", not re.search(r"\bAI\b", text))

print("== it ships, and it is pointed to ==")
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    check("%s bundles it" % spec, 'os.path.join(ROOT, "%s"), "."' % NAME in read("build", spec))
iss = read("build", "installer.iss")
check("the installer puts it beside the program", 'Source: "..\\%s"' % NAME in iss)
check("and takes it away again on uninstall", "DeleteFile(Base + '%s');" % NAME in iss)
check("the README's Licence section says it", NAME in read("README.md").split("## Licence", 1)[-1])
check("the voice folder says it", os.path.isfile(os.path.join(REPO, "voice", "README.txt"))
      and NAME in read("voice", "README.txt"))
check("About says it", "all rights reserved" in read("edsmt.py").split("def about_text", 1)[-1][:1500])

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
