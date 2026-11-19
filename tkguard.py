"""A closed window takes its timers with it.

The toolkit names a callback by where it sits in memory. When a widget is
destroyed its callbacks are deleted, but a timer it had waiting is not, and
the next callback made can be given the freed name. The timer then runs
that one instead: something on screen happens that nobody asked for.

install() makes destroying any widget cancel the timers still waiting for
it and for everything inside it. Those timers could only have failed (their
callbacks are deleted with the widget), so nothing that worked is lost.
"""
import functools
import tkinter as tk

# None where the toolkit is a stand-in with no widgets of its own (the
# headless tests): there is then nothing to guard, and install() says so by
# doing nothing rather than stopping the program from starting.
_BASE = getattr(tk, "BaseWidget", None)
ORIGINAL = getattr(_BASE, "destroy", None)
_ERRORS = (getattr(tk, "TclError", RuntimeError), AttributeError, RuntimeError)
_depth = [0]


def _commands_under(widget):
    """The names of every callback filed under `widget` or anything in it."""
    names, todo = set(), [widget]
    while todo:
        one = todo.pop()
        names.update(getattr(one, "_tclCommands", None) or ())
        todo.extend(list((getattr(one, "children", None) or {}).values()))
    return names


def cancel_timers(widget):
    """Cancel every waiting timer whose callback belongs to `widget` or to
    anything inside it. Returns how many. Never raises."""
    try:
        names = _commands_under(widget)
        if not names:
            return 0
        interp = widget.tk
        jobs = interp.splitlist(interp.call("after", "info"))
    except _ERRORS:
        return 0
    cancelled = 0
    for job in jobs:
        try:
            script = interp.splitlist(interp.call("after", "info", job))[0]
            if script in names:
                interp.call("after", "cancel", job)
                cancelled += 1
        except _ERRORS + (IndexError,):
            continue        # fired or cancelled meanwhile
    return cancelled


def _destroy(self):
    # Once, at the widget the destroying starts from: its children are
    # destroyed inside this call and are already covered.
    if _depth[0] == 0:
        cancel_timers(self)
    _depth[0] += 1
    try:
        return ORIGINAL(self)
    finally:
        _depth[0] -= 1


if ORIGINAL is not None:
    functools.update_wrapper(_destroy, ORIGINAL)


def installed():
    return _BASE is not None and _BASE.destroy is _destroy


def install():
    """From now on every widget takes its waiting timers with it. Returns
    whether it is in place: False only where there are no real widgets."""
    if ORIGINAL is None:
        return False
    if not installed():
        _BASE.destroy = _destroy
    return True
