"""1.10042: the source zip holds the whole project, new files included.

The source offered with 1.10041 was missing nine files that were new in that
release. The zip was made from the files git tracked, and it was made before
the release was committed, so anything new was left out.

Now the zip is made by build/source_zip.py from what git tracks plus
anything new that git is not told to ignore, and the release is refused if
its source zip does not hold every file of the project.

    python tests/test_110042_sourcezip.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "build"))

import source_zip as SZ          # noqa: E402
import publish_release as PR     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


print("== the build uses it ==")
bat = read("BUILD.bat")
check("BUILD.bat makes the zip with the script", "build\\source_zip.py upload\\EDSMT-source.zip" in bat)
check("and stops the build if it could not", "if errorlevel 1 goto FAIL" in bat.split("source_zip.py")[1][:120])
check("the older way, which left new files out, has gone", "Compress-Archive" not in bat)
script = read("build", "source_zip.py")
check("it asks git for tracked files and new ones, never ignored ones",
      '"--cached"' in script and '"--others"' in script and '"--exclude-standard"' in script)

if shutil.which("git") is None:
    print("  SKIP  no git on this machine: the zip itself cannot be made here")
else:
    def git(folder, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", HOME=folder,
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
        done = subprocess.run(["git", "-C", folder] + list(args), capture_output=True, env=env)
        assert done.returncode == 0, done.stderr.decode()

    def put(folder, name, text="x\n"):
        path = os.path.join(folder, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    print("== what goes in ==")
    box = tempfile.mkdtemp(prefix="edsmt-sourcezip-")
    git(box, "init", "-q", "-b", "main")
    put(box, ".gitignore", "/upload/\n/dist/\nsettings.json\n*.log\n")
    put(box, "edsmt.py", "print('app')\n")
    put(box, "docs/GUIDE.md", "# guide\n")
    put(box, "tests/test_old.py")
    put(box, "gone.py")
    git(box, "add", "-A")
    git(box, "commit", "-q", "-m", "first")
    # The state BUILD.bat runs in: the next release's new files are there,
    # not yet committed; a tracked file has been deleted; local data lies about.
    put(box, "certstore.py", "NEW = 1\n")
    put(box, "tests/test_new.py")
    put(box, "edsmt.py", "print('app, changed')\n")
    os.remove(os.path.join(box, "gone.py"))
    put(box, "settings.json", '{"inara_key": "secret"}\n')
    put(box, "crash.log")
    put(box, "dist/EDSMT.exe", "binary")
    names = SZ.listed(box)
    check("tracked files are in", "edsmt.py" in names and "docs/GUIDE.md" in names and "tests/test_old.py" in names, names)
    check("files new in this release are in, before they are committed",
          "certstore.py" in names and "tests/test_new.py" in names, names)
    check("a commander's settings, logs and builds are not",
          not [n for n in names if n in ("settings.json", "crash.log", "dist/EDSMT.exe")], names)
    check("a file that has been deleted is not", "gone.py" not in names)
    check("names use / and come in order", names == sorted(names) and not [n for n in names if "\\" in n])

    target = os.path.join(box, "upload", "EDSMT-source.zip")
    made = SZ.make(target, box)
    with zipfile.ZipFile(target) as held:
        inside = held.namelist()
        body = held.read("edsmt.py").decode()
    check("the zip holds exactly those files", inside == names == made, inside)
    check("as they are now, not as they were committed", body == "print('app, changed')\n", body)
    check("and no half-written file is left beside it", os.listdir(os.path.dirname(target)) == ["EDSMT-source.zip"])
    check("the zip itself is not in the next zip", "upload/EDSMT-source.zip" not in SZ.listed(box))
    check("a whole zip has nothing missing", SZ.missing(target, box) == [])

    print("== a zip made too early is refused ==")
    early = os.path.join(box, "upload", "early.zip")
    with zipfile.ZipFile(early, "w") as held:
        for name in ("edsmt.py", "docs\\GUIDE.md", "tests\\test_old.py", ".gitignore"):
            held.writestr(name, "x")
    gone = SZ.missing(early, box)
    check("what it lacks is named", gone == ["certstore.py", "tests/test_new.py"], gone)
    check("an older zip's backslash names are read as the same files", "docs/GUIDE.md" not in gone)
    os.replace(early, target)
    said = PR.source_problems(os.path.join(box, "upload"), box)
    check("the release is not published with it", len(said) == 1 and "missing 2" in said[0]
          and "certstore.py" in said[0] and "BUILD.bat" in said[0], said)
    SZ.make(target, box)
    check("made again, it may go", PR.source_problems(os.path.join(box, "upload"), box) == [])
    with open(target, "wb") as handle:
        handle.write(b"not a zip")
    check("a file that is not a zip at all is refused too", len(PR.source_problems(os.path.join(box, "upload"), box)) == 1)

    print("== where git cannot say ==")
    bare = tempfile.mkdtemp(prefix="edsmt-sourcezip-none-")
    check("outside a repository nothing is listed", SZ.listed(bare) is None)
    try:
        SZ.make(os.path.join(bare, "x.zip"), bare)
        check("and no empty zip is made", False)
    except RuntimeError:
        check("and no empty zip is made", not os.path.exists(os.path.join(bare, "x.zip")))
    os.makedirs(os.path.join(bare, "upload"))
    with open(os.path.join(bare, "upload", "EDSMT-source.zip"), "wb") as handle:
        handle.write(b"anything")
    check("the release check keeps quiet there rather than guess", PR.source_problems(os.path.join(bare, "upload"), bare) == [])

    def no_git(*_args, **_kwargs):
        raise OSError("no git")
    check("a machine with no git is the same", SZ.listed(box, run=no_git) is None)

print("== run with the rest ==")
check("this file is in the list", "test_110042_sourcezip.py" in read("tests", "run_all.py"))

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
