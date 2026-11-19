"""1.10042: the build workflow - what is kept, and from what.

  - the file is YAML, and has the shape a runner needs;
  - build artifacts are uploaded ONLY for a tag and for a run started by hand,
    never for every push or pull request (the build and the checks still run
    on every one, so a broken build is caught);
  - a tag leaves the two Windows programs (EDSMT-Setup.exe and EDSMT.exe)
    and the Linux file as artifacts, so a signing service can sign what CI
    built from the tag;
  - the streamer-mode check that raced a background status line on GitHub's
    Windows machine (#373) reads what it was told at once, and does not
    run the window's loop first;
  - BUILD.bat, the desk build, still builds and runs the suite as it did.

    python3.12 tests/test_110042_workflow.py
"""
import io
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
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


TAG_OR_HAND = "github.event_name == 'workflow_dispatch' || startsWith(github.ref, 'refs/tags/')"
text = read(".github", "workflows", "build.yml")

print("== the file parses ==")
try:
    import yaml
except ImportError:
    yaml = None
doc = None
if yaml is not None:
    try:
        doc = yaml.safe_load(text)
        check("it is YAML (PyYAML read it)", isinstance(doc, dict))
    except yaml.YAMLError as exc:
        check("it is YAML (PyYAML read it)", False, exc)
else:
    print("  NOTE  PyYAML is not installed here: a structural reading of the text is used")
    check("no tabs, and every line's indent is even",
          "\t" not in text and all((len(l) - len(l.lstrip(" "))) % 2 == 0
                                   for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")))
if doc is not None:
    triggers = doc.get("on", doc.get(True))
    check("it runs on pushes, tags, pull requests and by hand",
          isinstance(triggers, dict) and {"push", "pull_request", "workflow_dispatch"} <= set(triggers)
          and triggers["push"].get("tags") == ["v*"], triggers)
    jobs = doc.get("jobs") or {}
    check("three jobs: windows, linux, release", set(jobs) == {"windows", "linux", "release"}, list(jobs))
    check("every job has a runner and steps",
          all(j.get("runs-on") and isinstance(j.get("steps"), list) and j["steps"] for j in jobs.values()))
    check("every step does one thing: a run or a uses",
          all(("run" in st) != ("uses" in st) for j in jobs.values() for st in j["steps"]))
else:
    jobs = None
check("the three job names are there in the text", all("\n  %s:\n" % j in text
      for j in ("windows", "linux", "release")))

print("== artifacts only for a tag or a run by hand ==")
uploads = re.findall(r"(?:^|\n)((?:      - name:[^\n]*\n)?(?:        if:[^\n]*\n)?[^\n]*upload-artifact@[^\n]*(?:\n        [^\n]*)*)", text)
check("there are three uploads (two Windows, one Linux)", len(uploads) == 3, len(uploads))
check("every upload is held back to a tag or a run by hand",
      all(TAG_OR_HAND in u for u in uploads), [u[:60] for u in uploads if TAG_OR_HAND not in u])
check("no upload has a branch push or pull request condition of its own",
      "github.event_name == 'push'" not in text)
if doc is not None:
    ups = [(name, st) for name, j in jobs.items() for st in j["steps"]
           if str(st.get("uses", "")).startswith("actions/upload-artifact")]
    check("read as YAML: every upload step carries the condition",
          len(ups) == 3 and all(st.get("if") == TAG_OR_HAND for _n, st in ups), ups)
    names = sorted(st["with"]["name"] for _n, st in ups)
    check("the artifacts are EDSMT-linux, EDSMT-windows and EDSMT-windows-programs",
          names == ["EDSMT-linux", "EDSMT-windows", "EDSMT-windows-programs"], names)
    programs = [st for _n, st in ups if st["with"]["name"] == "EDSMT-windows-programs"][0]
    check("the programs artifact holds the Setup and the portable file, and fails if one is missing",
          "upload/EDSMT-Setup.exe" in programs["with"]["path"] and "upload/EDSMT.exe" in programs["with"]["path"]
          and programs["with"].get("if-no-files-found") == "error", programs)
check("it says so at the top", "keeps no files" in text and "signing service" in text)

print("== what a tag builds ==")
windows = text.split("\n  windows:\n")[1].split("\n  linux:\n")[0]
linux = text.split("\n  linux:\n")[1].split("\n  release:\n")[0]
check("the Windows job builds the folder build, the portable file and Setup",
      "build/EDSMT.spec" in windows and "build/EDSMT-onefile.spec" in windows and "iscc" in windows.lower()
      and "Copy-Item dist\\EDSMT.exe upload\\EDSMT.exe" in windows
      and "upload\\EDSMT-Setup.exe" in windows)
check("the Linux job builds the single file", "build/EDSMT-onefile.spec" in linux
      and "EDSMT-linux-x86_64.tar.gz" in linux)
check("the checks and the builds still run on every push (nothing is skipped for a branch)",
      "tests/run_all.py" in windows and "tests/run_all.py" in linux
      and not re.search(r"- name: Run the tests\n\s+if:", text))
check("the tag's release still needs only the Linux build", re.search(r"needs:\s*\[\s*linux\s*\]", text))

print("== the racing streamer check (#373) ==")
streamer = read("tests", "test_110040_streamer.py")
mark = streamer.index('app.say("Arrived at %s - 3 mining locations" % BODY)')
after = streamer[mark:mark + 900]
check("it reads the status line at once after say(), with no loop run between",
      "at_once = app.status.cget(\"text\")" in after
      and "pump(" not in after.split("at_once")[0], after[:200])
check("and says why (#373)", "#373" in after)

print("== the desk build is as it was ==")
bat = read("BUILD.bat")
check("BUILD.bat still builds both specs and runs the suite",
      "EDSMT.spec" in bat and "EDSMT-onefile.spec" in bat and "run_all.py" in bat
      and "installer.iss" in bat)

print()
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
