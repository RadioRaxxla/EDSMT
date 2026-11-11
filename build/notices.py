"""Write THIRD-PARTY-NOTICES.txt: the licences of what EDSMT is built with.

    python build/notices.py            write the file from the libraries installed here
    python build/notices.py --check    say whether the file names every library in requirements.txt

Run it again when requirements.txt changes or a library moves on a major
version, and commit the result. The texts are read from the installed
libraries themselves, so nothing here is typed by hand.
"""
import importlib.metadata as metadata
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "THIRD-PARTY-NOTICES.txt")

HEAD = """EDSMT - third-party notices

EDSMT itself is free software under the GNU General Public License,
version 3 (GPL-3.0): see LICENSE. It is built with the work of others, listed
here with the licence each is given under. These notices cover the Windows
installer, the single-file build, the Linux build and the source.
"""

# (name as pip knows it, licence, where it lives, note)
LIBRARIES = (
    ("customtkinter", "MIT License", "https://github.com/TomSchimansky/CustomTkinter", ""),
    ("darkdetect", "BSD 3-Clause License", "https://github.com/albertosottile/darkdetect",
     "Used by customtkinter."),
    ("packaging", "Apache License 2.0 or BSD 2-Clause License", "https://github.com/pypa/packaging",
     "Used by customtkinter."),
    ("Pillow", "MIT-CMU License", "https://github.com/python-pillow/Pillow",
     "The text below is Pillow's own and also covers the libraries built into it."),
    ("python-xlib", "GNU Lesser General Public License, version 2.1 or later",
     "https://github.com/python-xlib/python-xlib",
     "Linux build only. Unmodified; its source is at the address above."),
)


def _licence_text(name):
    """The licence file a library was installed with, or ""."""
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return "", ""
    for entry in dist.files or []:
        low = str(entry).lower()
        if "dist-info" in low and ("licen" in low or "copying" in low) and not low.endswith(".py"):
            try:
                with open(entry.locate(), encoding="utf-8", errors="replace") as handle:
                    return dist.version, handle.read()
            except OSError:
                continue
    return dist.version, ""


def _first(paths):
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError:
            continue
    return ""


def _python():
    base = sys.base_prefix
    version = "%d.%d" % sys.version_info[:2]
    return version, _first([os.path.join(base, "LICENSE.txt"),
                            os.path.join(base, "lib", "python" + version, "LICENSE.txt"),
                            "/usr/share/doc/python%s/copyright" % version])


def _tcl():
    try:
        import tkinter
        version = str(tkinter.TclVersion)
    except ImportError:
        version = ""
    base = sys.base_prefix
    return version, _first([os.path.join(base, "tcl", "tcl" + version, "license.terms"),
                            os.path.join(base, "lib", "tcl" + version, "license.terms"),
                            "/usr/share/doc/libtcl%s/copyright" % version])


def compose(entries):
    """The whole file from (name, version, licence, address, text) entries."""
    out = [HEAD.rstrip("\n"), ""]
    for name, version, licence, address, text in entries:
        title = ("%s %s" % (name, version)).strip()
        out += ["=" * 76, title, "Licence: " + licence, address, "=" * 76, ""]
        body = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        out.append(body if body else
                   "The licence text could not be read on the machine that made this file; "
                   "it is at the address above.")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def gather():
    entries = []
    for name, licence, address, note in LIBRARIES:
        version, text = _licence_text(name)
        if note and text:
            text = note + "\n\n" + text
        entries.append((name, version, licence, address, text))
    version, text = _python()
    entries.append(("Python", version, "Python Software Foundation License",
                    "https://docs.python.org/3/license.html", text))
    version, text = _tcl()
    entries.append(("Tcl/Tk", version, "Tcl/Tk licence (BSD style)",
                    "https://www.tcl-lang.org/software/tcltk/license.html", text))
    return entries


def missing():
    """Libraries in requirements.txt the file does not name."""
    try:
        with open(OUT, encoding="utf-8") as handle:
            have = handle.read().lower()
    except OSError:
        have = ""
    out = []
    with open(os.path.join(REPO, "requirements.txt"), encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = line.replace("<", "=").replace(">", "=").replace(";", "=").split("=")[0].strip()
            if "\n" + name.lower() + " " not in have and "\n" + name.lower() + "\n" not in have:
                out.append(name)
    return out


if __name__ == "__main__":
    if "--check" in sys.argv:
        gone = missing()
        print("names every library" if not gone else "does not name: " + ", ".join(gone))
        raise SystemExit(1 if gone else 0)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(compose(gather()))
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
