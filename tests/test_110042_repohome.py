"""1.10042: every link to the source points at RadioRaxxla/EDSMT.

The repository moved from a personal account to the Radio Raxxla
organisation on 14 November 2026. GitHub redirects the old address, but the
app, the page, the README and the release tools should name the new one.

    python tests/test_110042_repohome.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "build"))

NEW = "RadioRaxxla/EDSMT"
OLD = "TheAnnouncer" + "/EDSMT"

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


print("== the files people read ==")
for parts in (("README.md",), ("site", "index.html"), ("welcome.py",), ("edsmt.py",)):
    text = read(*parts)
    name = "/".join(parts)
    check(name + " names " + NEW, NEW in text)
    check(name + " no longer names the old address", OLD not in text,
          [line.strip() for line in text.splitlines() if OLD in line][:3])

print("== the app ==")
import welcome as W          # noqa: E402
check("the welcome window's links start at the new address",
      W.REPO_URL == "https://github.com/" + NEW, W.REPO_URL)
check("so do the guide, issues and changelog links",
      all(url.startswith("https://github.com/" + NEW + "/")
          for url in (W.GUIDE_URL, W.ISSUES_URL, W.CHANGELOG_URL)))

print("== the release tools ==")
import release_notes as RN   # noqa: E402
import publish_release as PR  # noqa: E402
check("release notes link the new address", RN.REPO_NAME == NEW, RN.REPO_NAME)
check("the release goes to the new address", PR.REPO_NAME == NEW, PR.REPO_NAME)

print("== nothing public names the old address ==")
skip_dirs = {".git", "__pycache__", "build_out", "dist", "upload"}
found = []
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for name in files:
        if name == "CHANGELOG.md" or name == os.path.basename(__file__):
            continue
        path = os.path.join(root, name)
        try:
            with open(path, encoding="utf-8") as handle:
                if OLD in handle.read():
                    found.append(os.path.relpath(path, REPO))
        except (UnicodeDecodeError, OSError):
            continue
check("no file outside the changelog names it", not found, found)

print("== run with the rest ==")
check("this file is in the list", "test_110042_repohome.py" in read("tests", "run_all.py"))

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
