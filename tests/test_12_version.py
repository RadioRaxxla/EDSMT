"""1.2: the version is called 1.2, and every older copy is still offered it.

His words, 19 Nov: "That way we can call it v1.2 and that way the next would
be v1.201". Versions are compared number by number, so a plain "1.2" would
read as (1, 2), below 1.10042, and no copy would ever be offered it. The
build is 1.20000 underneath - what the update check, version.json, the
installer and Windows' file details carry - and 1.2 wherever a person reads
it: the window, the cards, the patch notes, the tag and the release.

    python3 tests/test_12_version.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "build"))

import edonline as EDO   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    return open(os.path.join(REPO, *parts), encoding="utf-8").read()


print("== the number underneath and the one people read ==")
check("1.20000 reads as 1.2", EDO.shown_version("1.20000") == "1.2")
check("the next, 1.20100, reads as 1.201", EDO.shown_version("1.20100") == "1.201")
check("and 1.20110 as 1.2011", EDO.shown_version("1.20110") == "1.2011")
check("older ones read as they always did", EDO.shown_version("1.10042") == "1.10042"
      and EDO.shown_version("1.10040") == "1.10040")
check("nothing odd breaks it", EDO.shown_version("") == "" and EDO.shown_version("2") == "2")
check("this build is 1.20000 underneath", EDO.APP_VERSION == "1.20000", EDO.APP_VERSION)
check("and 1.2 to read", EDO.SHOWN_VERSION == "1.2", EDO.SHOWN_VERSION)
check("every older copy is offered it", EDO.is_newer("1.20000", "1.10042")
      and EDO.is_newer("1.20000", "1.10041"))
check("a plain 1.2 would not have been", not EDO.is_newer("1.2", "1.10042"))
check("and 1.201 after it is offered to 1.2", EDO.is_newer("1.20100", "1.20000"))

print("== the files that carry the number ==")
iss = read("build", "installer.iss")
info = read("build", "version_info.txt")
check("installer", '#define AppVersion "1.20000"' in iss and "VersionInfoVersion=1.20000.0.0" in iss)
check("Windows file details (each part under 65,536)", "filevers=(1,20000,0,0)" in info
      and "'FileVersion', '1.20000.0.0'" in info, info[:300])
check("the patch notes' heading is the one people read",
      read("CHANGELOG.md").split("\n## ", 1)[1].split("\n", 1)[0].strip() == "1.2")

print("== the release: tag v1.2, titled EDSMT 1.2 ==")
import release_notes as RN      # noqa: E402
import publish_release as PR    # noqa: E402
check("the notes come from the 1.2 entry", RN.entry("1.2") and RN.entry("1.20000") == RN.entry("1.2"))
ok = subprocess.run([sys.executable, os.path.join(REPO, "build", "release_notes.py"), "v1.2"],
                    capture_output=True, text=True)
check("the tag v1.2 is this build", ok.returncode == 0 and "1.2" in ok.stdout, ok.stderr)
bad = subprocess.run([sys.executable, os.path.join(REPO, "build", "release_notes.py"), "v1.3"],
                     capture_output=True, text=True)
check("another tag is refused", bad.returncode != 0)
cmds = PR.commands("1.20000", False, "notes.md", "upload")
check("published as tag v1.2, titled EDSMT 1.2", cmds[0][3] == "v1.2" and "EDSMT 1.2" in cmds[0], cmds[0])
import inspect   # noqa: E402
check("and looked for under v1.2", '"v" + shown(version)' in inspect.getsource(PR.release_exists))

print("== where people read it ==")
app = read("edsmt.py")
check("Settings says Version 1.2", '"Version %s" % SHOWN_VERSION' in app)
check("the welcome window and What's new are 1.2", "What's new in \" + SHOWN_VERSION" in app
      and "WL.read_whats_new(shipped_file(\"CHANGELOG.md\"), SHOWN_VERSION)" in app)
check("the session card says 1.2", "badge=badge, version=SHOWN_VERSION" in app)
site = read("build", "site.py")
check("the download page says 1.2, version.json keeps 1.20000",
      'fill(page, "VERSION", shown(now))' in site and '"version": now' in site)

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
