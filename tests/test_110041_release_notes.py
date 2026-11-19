"""1.10041: the notes on a GitHub release are short.

The release page used to carry the whole CHANGELOG entry, and anything that
reposts a release (a Discord card, a feed reader) reposted all of it. Now
the release says what the version is in a few lines and links to the full
patch notes, which stay in CHANGELOG.md and on the website.

    python tests/test_110041_release_notes.py
"""
import io
import os
import subprocess
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


LEAD = """Fixes, and nothing else: finds always carry a name, and Inara works again.

### Fixed

- **A find never goes up without the CMDR name.** A long paragraph of detail
  that belongs in the patch notes and not on a card.
- **Inara.** Another long paragraph.

### Changed

- Something else, at length.
"""
HEADINGS = "\n".join("### New — thing %d\n\n- **Thing %d** at length, with the detail.\n" % (n, n)
                     for n in range(1, 13))

print("== a version with a line of its own at the top ==")
short = RN.brief(LEAD, "9.99999")
check("the release says that line", short.startswith("Fixes, and nothing else: finds always carry a name"), short[:80])
check("and not the detail under the headings", "A long paragraph" not in short and "at length" not in short, short)
check("it links to the full patch notes for that version",
      "https://github.com/RadioRaxxla/EDSMT/blob/v9.99999/CHANGELOG.md" in short, short)
check("it says which download is which", "EDSMT-Setup.exe" in short and "EDSMT.exe" in short
      and "EDSMT-linux-x86_64.tar.gz" in short, short)
check("and what SmartScreen will do", "SmartScreen" in short and "Run anyway" in short, short)
check("no headings a card would show as hashes", "###" not in short, short)

print("== a version with no such line: its headings, a few of them ==")
short = RN.brief(HEADINGS, "9.99999")
check("the first headings are listed", "- New — thing 1\n" in short and "- New — thing %d\n" % RN.BRIEF_MOST in short, short)
check("the rest are counted, not listed", "thing %d" % (RN.BRIEF_MOST + 1) not in short
      and "and %d more" % (12 - RN.BRIEF_MOST) in short, short)
check("still short enough for one card", len(short) <= RN.BRIEF_CHARS, len(short))

print("== nothing but bullets: still something to say ==")
short = RN.brief("- **One fix.** Detail.\n- **Another.** Detail.\n", "9.99999")
check("it points at the patch notes", "CHANGELOG.md" in short and len(short) <= RN.BRIEF_CHARS, short)

print("== a very long opening line is cut at a sentence, not mid-word ==")
long_lead = ("This is a sentence about the release. " * 80) + "\n\n### Fixed\n\n- x\n"
short = RN.brief(long_lead, "9.99999")
check("under the limit", len(short) <= RN.BRIEF_CHARS, len(short))
check("ends its summary on a full stop", "release.\n" in short, short[:200])

print("== every released version stays short ==")
text = io.open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8").read()
versions = [line[3:].split()[0] for line in text.splitlines() if line.startswith("## ")][:6]
check("the changelog was read", len(versions) >= 3, versions)
for version in versions:
    body = RN.entry(version)
    made = RN.brief(body, version) if body else ""
    check("%s: short, with its link" % version, body is not None and 0 < len(made) <= RN.BRIEF_CHARS
          and ("/v%s/CHANGELOG.md" % version) in made, len(made))

print("== the tools use it ==")
now = RN.built_version() if hasattr(RN, "built_version") else ""
check("the tool knows the version in the tree", bool(now), now)
ran = subprocess.run([sys.executable, os.path.join(REPO, "build", "release_notes.py"), now],
                     capture_output=True, text=True, encoding="utf-8")
check("release_notes.py prints the short notes", ran.returncode == 0 and len(ran.stdout) <= RN.BRIEF_CHARS + 2
      and "CHANGELOG.md" in ran.stdout, (ran.returncode, len(ran.stdout), ran.stderr[-200:]))
full = subprocess.run([sys.executable, os.path.join(REPO, "build", "release_notes.py"), now, "--full"],
                      capture_output=True, text=True, encoding="utf-8")
check("--full still prints the whole entry", full.returncode == 0 and len(full.stdout) > len(ran.stdout),
      (full.returncode, len(full.stdout)))
src = io.open(os.path.join(REPO, "build", "publish_release.py"), encoding="utf-8").read()
check("the publisher writes the short notes", "brief(" in src and "entry(version) + \"\\n\" + FOOTER" not in src)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
