"""A table as a CSV file Excel opens (1.10042).

UTF-8 with a byte-order mark, so a spreadsheet reads the accents and the
dashes rather than guessing, and CRLF line ends. A cell that would be read as
a formula - one that starts with = or @ - is written as text. Used for the
sessions on Earnings and what is shown in Find. Pure file work, no window.
"""
import csv
import io
import time


def safe_cell(text):
    """The cell as it is written: a leading = or @ is made plain text."""
    text = "" if text is None else str(text)
    if text[:1] in ("=", "@"):
        return "'" + text
    return text


def to_text(headers, rows):
    """The whole file as text, BOM first. `rows` are lists of cell text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([safe_cell(h) for h in headers])
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return "﻿" + buffer.getvalue()


def write(path, headers, rows):
    """Write the file. Returns the number of rows; raises OSError."""
    text = to_text(headers, rows)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return len(rows)


def file_name(what, now=None):
    """EDSMT <what> - 2026-11-18 1005.csv, safe on Windows."""
    stamp = time.strftime("%Y-%m-%d %H%M", time.localtime(now or time.time()))
    clean = "".join(c for c in str(what) if c not in '\\/:*?"<>|').strip() or "table"
    return "EDSMT %s - %s.csv" % (clean, stamp)
