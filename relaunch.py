"""Starting a fresh copy of the program, or its update, from the running one.

The one-file program unpacks itself into a temporary folder when it starts
and removes that folder when it closes. It also tells every program it
starts where the folder is, so that a helper of its own can share it. A
second copy of the program is not a helper: started that way it used the
first copy's folder, the first copy then closed and took the folder with
it, and the second was left without its own files - no voice, no way out
to the network, and Windows saying a temporary directory could not be
removed.

The packager's answer is one word in the new program's environment,
PYINSTALLER_RESET_ENVIRONMENT=1, which tells it to unpack for itself. That
word is said here, and anything in the environment that still points into
the closing copy's folder is left out, so an installer started from here
does not hand it on either.
"""
import os
import shutil
import subprocess
import sys

RESET = "PYINSTALLER_RESET_ENVIRONMENT"
# A program of its own on Windows: no console shared with this one, and not
# closed with it (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP).
WINDOWS_FLAGS = 0x00000008 | 0x00000200


def unpack_folder():
    """Where this copy unpacked itself, or "" when it runs from source or
    from a folder of its own."""
    return str(getattr(sys, "_MEIPASS", "") or "")


def fresh_environment(environ=None, unpacked=None):
    """The environment a new copy, or the installer, is started with.

    A copy of `environ` (the real one when none is given) with the reset
    word set and every value that points into `unpacked` (this copy's own
    unpack folder when none is given) left out. `environ` is not changed.
    """
    env = dict(os.environ if environ is None else environ)
    folder = unpack_folder() if unpacked is None else str(unpacked or "")
    if folder:
        inside = os.path.normcase(os.path.normpath(folder))
        for name in list(env):
            value = os.path.normcase(os.path.normpath(str(env[name] or "")))
            if value == inside or value.startswith(inside + os.sep):
                del env[name]
    env[RESET] = "1"
    return env


def start(command, popen=None, environ=None, unpacked=None, windows=None):
    """Start `command` as a program of its own and return it.

    Raises what starting a program raises (OSError); the caller says so to
    the commander. `popen`, `environ`, `unpacked` and `windows` are for the
    checks; the app passes the command alone.
    """
    on_windows = (os.name == "nt") if windows is None else bool(windows)
    run = subprocess.Popen if popen is None else popen
    return run(command, close_fds=True,
               creationflags=WINDOWS_FLAGS if on_windows else 0,
               env=fresh_environment(environ, unpacked))


# The program file an update replaced, kept beside the new one (1.10042) so
# Help > "Go back to the previous version" has something to go back to. One
# copy only: the next update replaces it. Portable build only - the installed
# build is a folder put down by Setup, and keeping its previous folder is not
# something that can be done safely from here.
PREVIOUS = ".previous"
ASIDE = ".old"


def previous_path(exe):
    return str(exe) + PREVIOUS


def has_previous(exe=None):
    """Whether a previous program file is kept beside `exe` (this one when
    none is given)."""
    exe = os.path.abspath(sys.executable) if exe is None else str(exe)
    return os.path.isfile(previous_path(exe))


def put_new(new_exe, exe=None):
    """Put the new single-file program where the running one is.

    A running program can be renamed but not overwritten, so the running
    one moves aside to EXE.previous - the one copy kept for going back, in
    place of any earlier one - and the new one is copied into its name. If
    the copy fails the old one is put back, so there is never a moment with
    no program at all. Where the previous file cannot be replaced (it is
    running), the old one goes to EXE.old instead, as before, and nothing is
    kept. Returns the path of the program."""
    exe = os.path.abspath(sys.executable) if exe is None else str(exe)
    aside = previous_path(exe)
    held = aside + ".keep"
    had = os.path.exists(aside)
    try:
        if had:
            os.replace(aside, held)
        os.replace(exe, aside)
    except OSError:
        if had and os.path.exists(held) and not os.path.exists(aside):
            os.replace(held, aside)
        aside, had = exe + ASIDE, False
        if os.path.exists(aside):
            os.remove(aside)
        os.replace(exe, aside)
    try:
        shutil.copy2(new_exe, exe)
    except Exception:
        os.replace(aside, exe)
        if had:
            os.replace(held, previous_path(exe))
        raise
    if had:
        try:
            os.remove(held)
        except OSError:
            pass
    return exe


def go_back(exe=None):
    """Put the previous program file back in the running one's place. The
    running one moves aside to EXE.old, which the next start removes. Raises
    FileNotFoundError when there is no previous file, OSError when the swap
    cannot be done; the running file is put back if it fails half way."""
    exe = os.path.abspath(sys.executable) if exe is None else str(exe)
    kept = previous_path(exe)
    if not os.path.isfile(kept):
        raise FileNotFoundError("there is no previous version kept")
    aside = exe + ASIDE
    if os.path.exists(aside):
        os.remove(aside)
    os.replace(exe, aside)
    try:
        os.replace(kept, exe)
    except Exception:
        os.replace(aside, exe)
        raise
    return exe
