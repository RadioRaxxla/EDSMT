"""1.201: the release card reads cleanly.

The 1.2 card in Discord read badly. The card is the GitHub release's short notes, and they carried the
CHANGELOG's line breaks, so Discord broke every sentence at the CHANGELOG's
80 columns and again at the card's own width ("the map / and / the scope").
The short notes now join each paragraph into one line, link the patch notes
by name, and say which download is which in plain words.

    python tests/test_1201_card.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "build"))

import release_notes as RN    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


WRAPPED = """My sites becomes one data window for everything you have recorded, the map and
the scope explain themselves, and every deposit says how many tonnes are left.

Thanks to the testers, whose reports are behind many of these.

### New

- **A thing.** At length.
"""

print("== a wrapped paragraph becomes one line ==")
short = RN.brief(WRAPPED, "9.99999")
lead = short.split("\n\n[Full patch notes]")[0] if "[Full patch notes]" in short else short
check("no line break inside a sentence", "map and\nthe scope" not in short
      and "the map and the scope explain themselves" in short, short[:200])
check("the two paragraphs stay two", lead.count("\n\n") == 1 and "\n\nThanks to the testers" in lead, lead)
check("no single line breaks left in the summary", not re.search(r"[^\n]\n[^\n]", lead), lead)

print("== the link and the downloads read as words ==")
check("the patch notes are a named link",
      "[Full patch notes](https://github.com/RadioRaxxla/EDSMT/blob/v9.99999/CHANGELOG.md)" in short, short)
foot = short.split("CHANGELOG.md)", 1)[-1]
check("the footer has no hard line breaks either", not re.search(r"[^\n]\n[^\n]", foot.strip()), foot)
check("it says which download is which", "EDSMT-Setup.exe" in foot and "EDSMT.exe" in foot
      and "EDSMT-linux-x86_64.tar.gz" in foot and "installer" in foot and "portable" in foot, foot)
check("and what to do when SmartScreen warns", "SmartScreen" in foot and "More info" in foot
      and "Run anyway" in foot, foot)
check("still one card's worth", len(short) <= RN.BRIEF_CHARS, len(short))

print("== 1.2's own card says what 1.2 is ==")
body = RN.entry("1.2")
made = RN.brief(body, "1.2") if body else ""
top = made.split("[Full patch notes]")[0]
check("the 1.2 entry was read", bool(body))
check("it is not 1.10042's paragraph", "My sites becomes one data window" not in top, top[:120])
for word in ("tonnes are left", "Still there?", "rig", "voices"):
    check("1.2's card names %r" % word, word in top, top)
check("and reads as lines, not a column", not re.search(r"[^\n]\n[^\n]", top.strip()), top)

print("== the line every copy shows when a version is out ==")
# "EDSMT 1.201 is out - Fixed." is what the first build of 1.201 would have
# said: the line was the entry's first heading, and that was a bare "Fixed".
import importlib.util    # noqa: E402
_spec = importlib.util.spec_from_file_location("edsmt_site_build", os.path.join(REPO, "build", "site.py"))
SB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SB)
BARE_ENTRY = """Fixes from a tester's reports, clearer names for the two buttons, and
more voices. Thanks to the tester.

### Fixed

- **A thing.** At length.

### Changed

- **Another.** Also at length.
"""
line = SB.headline_of(BARE_ENTRY)
check("a bare section name is not the line", line not in ("Fixed", "Changed", "New"), line)
check("the entry's first sentence is, whole, across its line break",
      line == "Fixes from a tester's reports, clearer names for the two buttons, and more voices", line)
check("a heading that says something is still the line",
      SB.headline_of("A lead.\n\n### New \u2014 one data window, a key to the map\n\n- **A.** B.")
      == "New \u2014 one data window, a key to the map")
check("an entry with nothing in it has none", SB.headline_of("") == "" and SB.headline_of("### Fixed") == "")
now = SB.headline()
check("this version's own line says what the version is",
      len(now.split()) >= 4 and now.strip().lower() not in SB.BARE_HEADINGS, now)
check("and fits the one line the app has for it", len(now) <= 110, (len(now), now))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
