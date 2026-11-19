"""1.10042: Export CSV on Earnings (sessions) and on Find's results - UTF-8
with a byte-order mark so Excel opens it.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_csvexport.py
"""
import csv
import faulthandler
import io
import os
import sys
import tempfile

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-csv42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import csvexport as CX   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


print("== the file ==")
headers = ["Started", "Mined", "Note"]
rows = [["2026-11-18 10:00", "57t: Platinum 40\nOsmium 17", "Bastnäsite – “quoted”, with a comma"],
        ["2026-11-18 11:00", "=1+1", "@home"]]
path = os.path.join(TMP, "out.csv")
count = CX.write(path, headers, rows)
raw = open(path, "rb").read()
check("it starts with the UTF-8 byte-order mark", raw.startswith(b"\xef\xbb\xbf"), raw[:6])
check("lines end CRLF", b"\r\n" in raw and raw.count(b"\r\n") >= 3)
back = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
check("it reads back as the table", back[0] == headers and back[1] == rows[0], back)
check("accents and dashes survive", "Bastnäsite – “quoted”" in raw.decode("utf-8"))
check("a cell with a new line is one cell", back[1][1] == rows[0][1])
check("a cell that would be a formula is text", back[2][1] == "'=1+1" and back[2][2] == "'@home", back[2])
check("the row count comes back", count == 2)
check("no rows is a header and nothing else", CX.to_text(["a"], []) == "﻿a\r\n")
name = CX.file_name("Rhino sessions", now=1794990000)
check("the file name is safe and dated", name.startswith("EDSMT Rhino sessions - 2026-") and name.endswith(".csv")
      and not any(c in name for c in '\\/:*?"<>|'), name)
check("a name with bad characters is cleaned", "/" not in CX.file_name("a/b"))
try:
    CX.write(os.path.join(TMP, "no", "such", "x.csv"), ["a"], [])
    check("an unwritable path raises OSError", False)
except OSError:
    check("an unwritable path raises OSError", True)

print("== the two windows ==")
import edsmt as A   # noqa: E402


class FakeEarnings:
    _rows = [{"id": 1}, {"id": 2}]
    _cell = staticmethod(A.EarningsWindow._cell)

    def _sorted(self, rows):
        return rows

    def _run_row(self, row):
        return [("Run %d" % row["id"],), ("57 t", None, 57), ("-",)]


h, r = A.EarningsWindow.csv_rows(FakeEarnings())
check("Earnings writes the headings it shows and each row's cell text",
      h == list(A.RUN_HEADERS) and r == [["Run 1", "57 t", "-"], ["Run 2", "57 t", "-"]], (h, r))


class FakeFind:
    _headers = ("System", "Body")
    _builder = staticmethod(lambda row: [(row[0],), (row[1], "#fff")])
    _cell = staticmethod(A.FindWindow._cell)

    def _visible(self):
        return [("Ega", "3 a"), ("Vela", "1")]

    def _sorted(self, rows):
        return list(reversed(rows))


h, r = A.FindWindow.csv_rows(FakeFind())
check("Find writes what is shown, in the order shown", h == ["System", "Body"]
      and r == [["Vela", "1"], ["Ega", "3 a"]], (h, r))
none = FakeFind()
none._builder = None
check("Find with no table has nothing to write", A.FindWindow.csv_rows(none) == ([], []))

print("== wiring ==")
src = read("edsmt.py")
check("both windows have an Export CSV button", src.count("command=self.export_csv") == 2
      , src.count("command=self.export_csv"))
check("nothing to export is said, not written", "Nothing to export yet." in src)
check("csvexport is in both build specs", all('"csvexport"' in read("build", s)
                                              for s in ("EDSMT.spec", "EDSMT-onefile.spec")))
check("the guide says it", "export csv" in read("docs", "GUIDE.md").lower())
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
