#!/usr/bin/env python3
"""Put this build's Windows files on the GitHub release for its tag.

    python build/publish_release.py            check only: says what it would do
    python build/publish_release.py --go       create or update the release

The website and the GitHub release offer the same build: the files BUILD.bat
made on the desk, which passed the whole suite on a real Windows desktop and
whose sizes and SHA-256 are in version.json. GitHub's own build of the tag
is a second check and makes the Linux file; it never replaces these. Before
1.10040 the two places could carry different exes under one version number.

It refuses to publish anything that does not match version.json, or a build
whose version is not the tag's. The release is named "EDSMT <version>" and
its notes come from CHANGELOG.md, the same words as the website.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
from release_notes import brief, entry, shown  # noqa: E402
import source_zip  # noqa: E402

REPO_NAME = "RadioRaxxla/EDSMT"
FILES = ("EDSMT-Setup.exe", "EDSMT.exe", "EDSMT-source.zip")
KINDS = {"installer": "EDSMT-Setup.exe", "portable": "EDSMT.exe"}


def built_version():
    text = io.open(os.path.join(REPO, "edonline.py"), encoding="utf-8").read()
    m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', text)
    return m.group(1) if m else ""


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def problems(upload):
    """Why these files must not be published, or [] when they may."""
    out = []
    version = built_version()
    info_path = os.path.join(upload, "version.json")
    try:
        with io.open(info_path, encoding="utf-8") as fh:
            info = json.load(fh)
    except (OSError, ValueError) as exc:
        return ["version.json in upload is missing or unreadable (%s) - run BUILD.bat" % exc]
    if info.get("version") != version:
        out.append("version.json says %s but the app is %s - run BUILD.bat"
                   % (info.get("version"), version))
    for name in FILES:
        if not os.path.isfile(os.path.join(upload, name)):
            out.append("%s is not in upload - run BUILD.bat" % name)
    for kind, name in KINDS.items():
        path = os.path.join(upload, name)
        want = info.get(kind) or {}
        if os.path.isfile(path) and want.get("sha256") != sha256(path):
            out.append("%s is not the file version.json describes" % name)
    if entry(version) is None:
        out.append("CHANGELOG.md has no entry for %s" % version)
    out += source_problems(upload)
    return out


def source_problems(upload, repo=REPO):
    """The source zip has to hold the whole project as it is now: 1.10041's
    was made before that release's new files were added, and went out
    without them. [] when it is whole, or when this is not a repository."""
    path = os.path.join(upload, "EDSMT-source.zip")
    if not os.path.isfile(path):
        return []                       # said already, above
    gone = source_zip.missing(path, repo)
    if not gone:
        return []
    return ["EDSMT-source.zip is missing %d of the project's files (%s%s) - run BUILD.bat again"
            % (len(gone), ", ".join(gone[:3]), ", ..." if len(gone) > 3 else "")]


def commands(version, exists, notes_path, upload):
    """The gh commands that publish `version`, in order. The tag and the
    title carry the version as people read it (v1.2, "EDSMT 1.2")."""
    tag = "v" + shown(version)
    files = [os.path.join(upload, name) for name in FILES]
    if exists:
        return [["gh", "release", "edit", tag, "-R", REPO_NAME,
                 "--title", "EDSMT " + shown(version), "--notes-file", notes_path],
                ["gh", "release", "upload", tag, "-R", REPO_NAME, "--clobber"] + files]
    return [["gh", "release", "create", tag, "-R", REPO_NAME, "--verify-tag",
             "--title", "EDSMT " + shown(version), "--notes-file", notes_path] + files]


def release_exists(version, run=subprocess.run):
    result = run(["gh", "release", "view", "v" + shown(version), "-R", REPO_NAME],
                 capture_output=True, text=True)
    return result.returncode == 0


def main(argv, run=subprocess.run, gh="gh"):
    upload = os.path.join(REPO, "upload")
    version = built_version()
    bad = problems(upload)
    if bad:
        for line in bad:
            print("  NOT PUBLISHED: " + line)
        return 1
    exists = release_exists(version, run)
    notes = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                        suffix=".md", delete=False)
    with notes:
        notes.write(brief(entry(version), shown(version)))
    todo = commands(version, exists, notes.name, upload)
    for cmd in todo:
        cmd[0] = gh
    if "--go" not in argv:
        print("check only - the release for %s %s; these would run:"
              % (version, "exists" if exists else "does not exist yet"))
        for cmd in todo:
            print("  " + " ".join(cmd[:4]) + " ...")
        return 0
    for cmd in todo:
        result = run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("  FAILED: %s\n%s" % (" ".join(cmd[:4]), result.stderr.strip()))
            return 1
    print("EDSMT %s published: %s" % (shown(version), ", ".join(FILES)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
