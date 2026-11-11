"""1.10041: the licences of what EDSMT is built with go out with it.

EDSMT is GPL-3.0 and is built with other people's work: Python and Tcl/Tk,
customtkinter, Pillow, and python-xlib on Linux. Each asks that its licence
travels with any copy. THIRD-PARTY-NOTICES.txt carries them, and every form
EDSMT ships in - the installer, the single file, the Linux file, the source -
takes it along.

    python tests/test_110041_notices.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "build"))

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


NAME = "THIRD-PARTY-NOTICES.txt"

print("== the file ==")
check("it is in the repository", os.path.isfile(os.path.join(REPO, NAME)))
text = read(NAME) if os.path.isfile(os.path.join(REPO, NAME)) else ""
needs = [line.split(">")[0].split("<")[0].split("=")[0].split(";")[0].strip()
         for line in read("requirements.txt").splitlines()
         if line.strip() and not line.lstrip().startswith("#")]
check("requirements.txt was read", len(needs) >= 3, needs)
for name in needs:
    check("it names %s" % name, re.search(r"(?im)^" + re.escape(name) + r"\b", text) is not None)
for name in ("Python", "Tcl/Tk"):
    check("it names %s" % name, re.search(r"(?m)^" + re.escape(name) + r"\b", text) is not None)
check("customtkinter's licence is there in full, with its copyright line",
      "MIT License" in text and "Tom Schimansky" in text and "WITHOUT WARRANTY OF ANY KIND" in text)
check("Pillow's is", "Python Imaging Library" in text and "Jeffrey 'Alex' Clark" in text)
check("python-xlib's is, and says where its source is",
      "GNU LESSER GENERAL PUBLIC LICENSE" in text and "github.com/python-xlib/python-xlib" in text)
check("Python's is", "PYTHON SOFTWARE FOUNDATION LICENSE" in text)
check("Tcl/Tk's is", "Regents of the University of California" in text)
check("it says what EDSMT's own licence is", "GPL-3.0" in text or "GNU General Public License" in text)
check("plain text a notepad can open", "\r" not in text and all(ord(c) < 0x2500 for c in text[:2000]))

print("== it travels with every form EDSMT ships in ==")
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    check("%s puts it in the bundle" % spec, NAME in read("build", spec))
check("the installer installs it beside the licence", NAME in read("build", "installer.iss"))
check("an uninstall takes it away again", read("build", "installer.iss").count(NAME) >= 2)
check("the Linux file carries it", NAME in read(".github", "workflows", "build.yml"))

print("== it can be made again when a library changes ==")
import notices as NT    # noqa: E402
made = NT.compose([("Example", "1.0", "MIT", "https://example.invalid", "Copyright (c) Somebody\nPermission...")])
check("the maker writes a heading for each library", "Example 1.0" in made and "Permission..." in made
      and "https://example.invalid" in made, made[:300])
check("and says what the file is for at the top", made.splitlines()[0].startswith("EDSMT"))
check("a library it cannot find is named, never dropped silently",
      "could not be read" in NT.compose([("Gone", "", "MIT", "https://example.invalid", "")]))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
