#!/usr/bin/env python3
"""Make EDSMT-source.zip: the source GPL-3.0 asks to be offered with a build.

    python build/source_zip.py upload/EDSMT-source.zip

The zip holds every file of the project that is in the repository, or is
about to be: what git tracks, and anything new that git is not told to
ignore. A commander's own data, the builds and this machine's own files are
all ignored, so none of them can get in.

Up to 1.10041 the zip was made from the tracked files alone, and it was made
before the release was committed - so the files that were new in a release
were left out of that release's source. They are in now.

Names inside the zip use "/", so it unpacks the same on Windows and Linux.
"""
import os
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def listed(repo=REPO, run=subprocess.run):
    """Every file the zip should hold, as repository paths with "/", in
    order. None when git cannot say (not a repository, or no git)."""
    try:
        done = run(["git", "-C", repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                   capture_output=True)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    names = [n for n in done.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
    # A file git still tracks but that has been deleted is not source any more.
    return sorted({n for n in names if os.path.isfile(os.path.join(repo, *n.split("/")))})


def make(target, repo=REPO, run=subprocess.run):
    """Write the zip. Returns the names put in it; raises RuntimeError when
    there is nothing to put in, so an empty zip is never offered."""
    names = listed(repo, run)
    if not names:
        raise RuntimeError("git lists no files here - is this the repository?")
    folder = os.path.dirname(os.path.abspath(target))
    os.makedirs(folder, exist_ok=True)
    partial = target + ".part"
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name in names:
            out.write(os.path.join(repo, *name.split("/")), name)
    os.replace(partial, target)
    return names


def missing(zip_path, repo=REPO, run=subprocess.run):
    """Files of the project that are not in the zip. [] when it is whole;
    None when git cannot say what the project holds."""
    names = listed(repo, run)
    if names is None:
        return None
    try:
        with zipfile.ZipFile(zip_path) as held:
            inside = {n.replace("\\", "/") for n in held.namelist()}
    except (OSError, zipfile.BadZipFile):
        return names
    return [n for n in names if n not in inside]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        names = make(argv[1])
    except (RuntimeError, OSError) as exc:
        print("  The source zip was not made: %s" % exc)
        return 1
    print("        %d files in %s" % (len(names), argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
