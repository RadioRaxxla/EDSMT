"""1.10042: EDSMT in numbers, on the EDSMT page.

How many deposits, mining locations, bodies and systems are on the community
map, how many commanders have shared a find, how many installs are in use
this week, what came in lately and the find furthest from Sol. The numbers
are the community map's own, asked for when the page opens. Nothing is
written into the page by hand, so the page can never show a number nobody
counted: until an answer arrives the whole section stays out of sight.

    python tests/test_110042_sitestats.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
page = io.open(os.path.join(REPO, "site", "index.html"), encoding="utf-8").read()

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def block(start, end):
    i = page.find(start)
    j = page.find(end, i)
    return page[i:j + len(end)] if i >= 0 and j >= 0 else ""


sec = block('<section class="section" id="numbers"', "</section>")

print("== the section ==")
check("the page has EDSMT in numbers", bool(sec) and "<h2>EDSMT in numbers</h2>" in sec)
check("straight after the top of the page, before What it does",
      0 < page.find("</header>", page.find('class="page-head hero"')) < page.find('id="numbers"') < page.find('id="what"'))
check("out of sight until the map answers", re.search(r'<section class="section" id="numbers"[^>]*\shidden', page) is not None)
check("it says where the numbers are from", "community map" in sec and "counts only" in sec.lower())

print("== what it counts ==")
WANT = [("deposits", "Deposits mapped"), ("sites", "Mining locations surveyed"), ("bodies", "Bodies"),
        ("systems", "Systems"), ("commanders", "Commanders who have shared a find"),
        ("installs", "Total installs"), ("active", "Installs in use this week"),
        ("finds7", "Finds in the last 7 days"),
        ("rigs", "Rig spots mapped"), ("commodities", "Commodities found")]
for key, words in WANT:
    tile = re.search(r'<div class="num" data-stat="%s"[^>]*>(.*?)</div>' % key, sec, re.S)
    check("%s: %s" % (key, words), tile is not None and words in tile.group(1), key)
    check("  no number is written in by hand", tile is not None and "<b></b>" in tile.group(1), key)
    check("  and it stays out of sight until it has one", tile is not None and " hidden" in tile.group(0).split(">")[0], key)
check("a line for the records: furthest from Sol, most found, mapping since", 'data-stats="records"' in sec)

print("== where the numbers come from ==")
# The site's own rules let its pages ask api.radioraxxla.com and not EDSMT's
# newer address, so the page says so on the line that names it.
check("asked at the address the site lets its pages ask",
      "var MAP = 'https://api.radioraxxla.com';" in sec and "not edsmt.radioraxxla.com" in sec)
check("the community map's own count", "ask(MAP + '/v1/stats')" in sec)
check("and, if that is not there, the totals the map already gives", "ask(MAP + '/v1/map/summary')" in sec)
check("no other address is asked", set(re.findall(r"https?://[^\s'\"<>)]+", sec)) <=
      {"https://api.radioraxxla.com", "https://edsmt.radioraxxla.com/live"},
      sorted(set(re.findall(r"https?://[^\s'\"<>)]+", sec))))
check("numbers are written the British way", "toLocaleString('en-GB')" in sec)
check("a name from the map is never put in as markup", "textContent" in sec and "innerHTML" not in sec)
check("a failure leaves the section out of sight, with no error shown", ".catch(" in sec)

print("== the styles ==")
style = block("<style>", "</style>")
check("the tiles are EDSMT's own, scoped like the rest", ".edsmt .numbers" in style and ".edsmt .num" in style)
check("out of sight means not drawn: the tiles' own display does not bring a hidden one back",
      ".edsmt #numbers[hidden],.edsmt .num[hidden]{display:none}" in style)

print("== run with the rest ==")
check("this file is in the list",
      "test_110042_sitestats.py" in io.open(os.path.join(HERE, "run_all.py"), encoding="utf-8").read())

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
