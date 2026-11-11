"""1.10041: the wing link is not called beta, and Rich Presence is described
by the words Discord shows.

The wing link was finished in 1.10040 (linked from the in-game wing, one
shared survey, pins split) and Settings and the guide still called it beta.
Rich Presence shows the name of EDSMT's Discord application on a profile:
"Playing Surface Mining with EDSMT".

    python tests/test_110041_words.py
"""
import io
import os

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


app, guide = read("edsmt.py"), read("docs", "GUIDE.md")
shown = [line.strip() for line in app.splitlines()
         if "(beta)" in line and ("_section(" in line or "_switch(" in line or "text=" in line)]
print("== the wing link ==")
check("nothing a commander reads in Settings calls a feature beta", not shown, shown)
check("the guide's heading is the wing link, plainly", "### The wing link\n" in guide
      and "wing link (beta)" not in guide.lower())
check("Settings still has the section, the automatic link and the code",
      '_section(body, "Wing link",' in app and '"wing_auto"' in app and '"wing_code"' in app)
check("the patch notes say so", "no longer called beta" in read("CHANGELOG.md").split("## 1.10040")[0])

print("== Rich Presence ==")
check("Settings says what Discord will show", "Playing Surface Mining with EDSMT" in app)
check("and so does the guide", "Playing Surface Mining\nwith EDSMT" in guide
      or "Playing Surface Mining with EDSMT" in guide)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
