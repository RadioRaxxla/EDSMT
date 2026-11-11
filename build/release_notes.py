#!/usr/bin/env python3
"""Print one version's notes for a GitHub release, from CHANGELOG.md.

    python build/release_notes.py 1.10041            the short notes
    python build/release_notes.py 1.10041 --full     the whole entry

The release page says what the version is in a few lines and links to the
full patch notes: anything that reposts a release reposts all of it, and a
whole CHANGELOG entry is no card (1.10041). The short notes are the entry's
own opening lines when it has some, its headings when it has not - so the
release, the changelog and the website still come from the same entry. A
tag with no entry for its version fails here, on purpose: a release nobody
wrote patch notes for is a release nobody can tell apart from the last one.
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOOTER = """
---

**EDSMT-Setup.exe** is the download - a normal installer, no admin needed.
**EDSMT.exe** is the same program as a single portable file.
**EDSMT-source.zip** is the source it was built from, as GPL-3.0 requires.
**EDSMT-linux-x86_64.tar.gz** is the Linux build: unpack it and run `EDSMT`
(or `bash RUN.sh` from the source). docs/LINUX.md says what differs.

Windows SmartScreen will warn on first run because the build is not code
signed. More info, then Run anyway. SECURITY.md explains that in full.
"""


REPO_NAME = "TheAnnouncer/EDSMT"
NOTES_URL = "https://github.com/" + REPO_NAME + "/blob/v%s/CHANGELOG.md"
BRIEF_MOST = 8          # headings listed before "and N more"
BRIEF_CHARS = 1500      # the whole of the short notes, at most

SHORT_FOOTER = """**EDSMT-Setup.exe** installs it. **EDSMT.exe** is the same program as one \
portable file. **EDSMT-linux-x86_64.tar.gz** is the Linux build. Windows \
SmartScreen warns on first run because the build is not code signed: More \
info, then Run anyway.
"""


def _cut(text, most):
    """`text` in at most `most` characters, ended on a sentence where one
    ends inside the limit, else on a word."""
    text = text.strip()
    if len(text) <= most:
        return text
    head = text[:most]
    stop = max(head.rfind(". "), head.rfind(".\n"))
    if stop > most // 3:
        return head[:stop + 1]
    return head[:head.rfind(" ")].rstrip(",;:") + "..."


def brief(body, version):
    """The short notes for a release: what `body` (a CHANGELOG entry) says
    before its first heading, or its headings when it says nothing there,
    then where the full patch notes are and which download is which."""
    lead, headings = [], []
    for line in (body or "").splitlines():
        if line.startswith("### "):
            headings.append(line[4:].strip())
        elif not headings:
            lead.append(line)
    tail = "\n\nFull patch notes: " + (NOTES_URL % version) + "\n\n" + SHORT_FOOTER
    room = BRIEF_CHARS - len(tail)
    said = "\n".join(lead).strip()
    if said and not said.lstrip().startswith(("- ", "* ")):
        top = _cut(said, room)
    elif headings:
        shown = headings[:BRIEF_MOST]
        top = "\n".join("- " + h for h in shown)
        if len(headings) > len(shown):
            top += "\n- and %d more" % (len(headings) - len(shown))
        top = _cut(top, room)
    else:
        top = "EDSMT %s." % version
    return top + tail


def built_version():
    """The version the tree says it is, or ""."""
    found = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', io.open(
        os.path.join(REPO, "edonline.py"), encoding="utf-8").read())
    return found.group(1) if found else ""


def entry(version):
    """The body of the `## <version>` block, without its heading."""
    text = io.open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8").read()
    blocks = re.split(r"^## ", text, flags=re.M)[1:]
    for block in blocks:
        heading, _, body = block.partition("\n")
        if heading.strip().split()[0:1] == [version]:
            body = re.split(r"^---\s*$", body, flags=re.M)[0]
            return body.strip()
    return None


def main(argv):
    full = "--full" in argv[2:]
    if len(argv) < 2 or [a for a in argv[2:] if a != "--full"]:
        sys.exit("usage: release_notes.py <version> [--full]   e.g. 1.10041 or v1.10041")
    version = argv[1].strip().lstrip("vV")
    # The tag has to be the build. A tag of v1.10029 on a commit that still
    # says 1.10028 would publish one version's exe under another's notes.
    built = built_version()
    if built != version:
        sys.exit("the tag says %s but edonline.APP_VERSION is %s - run "
                 "build/bump.py first" % (version, built or "missing"))
    body = entry(version)
    if not body:
        sys.exit("CHANGELOG.md has no '## %s' entry - write the patch notes "
                 "before tagging the release." % version)
    out = (body + "\n" + FOOTER) if full else brief(body, version)
    # Bytes, so a console in another code page cannot spoil the dashes.
    sys.stdout.buffer.write(out.encode("utf-8"))


if __name__ == "__main__":
    main(sys.argv)
