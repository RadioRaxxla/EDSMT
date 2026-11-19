"""1.10042: the Powerplay tool and the Leaderboard no longer hold the window.

Players, 12 Nov: the Powerplay tool made the window stand still, and on some
PCs it stopped responding. Where it counts drew every system of the record
at once - up to 300 rows, every cell a widget of its own - and drew them all
again for every letter typed in its boxes and every time the record changed.
Where to sell and the Leaderboard were drawn the same way.

Now:
  - the record is searched on a thread of its own and the answer is handed
    back to the window, which says "Searching" meanwhile. One search at a
    time, only the newest answer is drawn, a failure is said in words on the
    page, and nothing is left running when the window or its tab closes;
  - all three tables are on the tree view the big tables use, twenty rows a
    page, with Previous and Next and a line such as "Page 2 of 7 - 132
    systems";
  - turning a page, or sorting, draws from the rows in hand and asks nobody
    for anything.

The first half is plain functions and needs no display. The second half
opens the windows on the real toolkit and says SKIP, out loud, without one.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_powerplay.py
"""
import faulthandler
import inspect
import io
import json
import os
import re
import sys
import tempfile
import threading
import time

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-pp42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import tableview as TV    # noqa: E402
import board as LB        # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    """Run the function under it; an exception is one failure, named."""
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=6)
        return fn
    return wrap


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


def wait_for(test, seconds=10.0):
    """Wait for a result, up to a deadline - never a fixed number of loops."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.01)
    return bool(test())


def answer_of(job, seconds=10.0):
    """The job's answer once it is in, or None at the deadline."""
    found = []
    wait_for(lambda: found.append(job.poll()) or found[-1] is not None, seconds)
    return found[-1] if found else None


# ---------------------------------------------------------------------------
# (i) Twenty rows a page, as plain functions
# ---------------------------------------------------------------------------

@section("a page is twenty rows: how many pages, which rows, and staying inside them")
def _pages():
    check("twenty rows a page", TV.PAGE_ROWS == 20, getattr(TV, "PAGE_ROWS", None))
    counts = [TV.page_count(n) for n in (0, 1, 20, 21, 40, 41, 132, 300)]
    check("pages for 0, 1, 20, 21, 40, 41, 132 and 300 rows",
          counts == [1, 1, 1, 2, 2, 3, 7, 15], counts)
    check("nonsense for a number of rows is one empty page",
          TV.page_count(None) == 1 and TV.page_count(-5) == 1 and TV.page_count("x") == 1)
    check("a page before the first is the first", TV.clamp_page(-3, 132) == 0)
    check("a page past the last is the last", TV.clamp_page(99, 132) == 6, TV.clamp_page(99, 132))
    check("a page inside stays where it is", TV.clamp_page(3, 132) == 3)
    check("with no rows there is only the first", TV.clamp_page(5, 0) == 0)
    check("and nonsense for a page is the first", TV.clamp_page("x", 132) == 0
          and TV.clamp_page(None, 132) == 0)
    rows = list(range(132))
    check("the first page is rows 1 to 20", TV.page_rows(rows, 0) == list(range(20)))
    check("the second is rows 21 to 40", TV.page_rows(rows, 1) == list(range(20, 40)))
    check("the last page holds what is left - 12 of 132",
          TV.page_rows(rows, 6) == list(range(120, 132)), TV.page_rows(rows, 6))
    check("a page past the end shows the last, never nothing",
          TV.page_rows(rows, 50) == list(range(120, 132)))
    check("no rows is an empty page", TV.page_rows([], 0) == [] and TV.page_rows(None, 3) == [])
    check("twenty rows is one full page and no second",
          TV.page_rows(list(range(20)), 0) == list(range(20))
          and TV.page_rows(list(range(20)), 1) == list(range(20)))
    check("no page is ever longer than twenty",
          all(len(TV.page_rows(list(range(n)), p)) <= 20
              for n in (0, 1, 19, 20, 21, 300) for p in range(-1, 17)))
    check("another size of page can be asked for",
          TV.page_count(11, 5) == 3 and TV.page_rows(list(range(11)), 2, 5) == [10])


@section("the line under the table, and whether Previous and Next have anywhere to go")
def _page_line():
    check("the page, the pages and the rows",
          TV.page_line(1, 132, "system", "systems") == "Page 2 of 7 - 132 systems",
          TV.page_line(1, 132, "system", "systems"))
    check("one row is one of them",
          TV.page_line(0, 1, "system", "systems") == "Page 1 of 1 - 1 system",
          TV.page_line(0, 1, "system", "systems"))
    check("nothing to show is no line at all", TV.page_line(0, 0, "system", "systems") == "")
    check("a page past the end reads as the last",
          TV.page_line(99, 132, "system", "systems") == "Page 7 of 7 - 132 systems")
    check("thousands are written with their comma",
          TV.page_line(0, 1500, "system", "systems") == "Page 1 of 75 - 1,500 systems",
          TV.page_line(0, 1500, "system", "systems"))
    check("left to itself it counts rows", TV.page_line(2, 51) == "Page 3 of 3 - 51 rows",
          TV.page_line(2, 51))
    check("on the first page only Next can go", TV.page_turns(0, 132) == (False, True))
    check("in the middle both can", TV.page_turns(3, 132) == (True, True))
    check("on the last only Previous", TV.page_turns(6, 132) == (True, False))
    check("one page: neither", TV.page_turns(0, 20) == (False, False)
          and TV.page_turns(0, 0) == (False, False))


@section("a new result set starts on page 1; the same one keeps its page")
def _page_reset():
    check("fresh results go back to page 1", TV.page_for(4, 132, fresh=True) == 0)
    check("the same results redrawn stay on their page", TV.page_for(4, 132, fresh=False) == 4)
    check("unless that page has gone: then the last there is",
          TV.page_for(4, 41, fresh=False) == 2, TV.page_for(4, 41, fresh=False))
    check("fresh is what it takes for granted", TV.page_for(4, 132) == 0)
    check("none of it touches a widget", "tkinter" not in read("tableview.py"))


# ---------------------------------------------------------------------------
# (ii) The search worker
# ---------------------------------------------------------------------------

try:
    import searchjob as SJ    # noqa: E402
except ImportError as _exc:
    SJ = None
    print("== the search worker ==")
    check("searchjob.py is there to import", False, _exc)


class Slow:
    """Stands in for whatever is searched: it waits at a gate, counts its
    calls and says how many were ever running at once."""

    def __init__(self):
        self.gate, self.entered = threading.Event(), threading.Event()
        self.calls, self.threads = [], []
        self.now = self.most = 0
        self._lock = threading.Lock()

    def __call__(self, what):
        with self._lock:
            self.now += 1
            self.most = max(self.most, self.now)
            self.calls.append(what)
            self.threads.append(threading.current_thread())
        self.entered.set()
        self.gate.wait(30)
        with self._lock:
            self.now -= 1
        return "answer to %s" % what


@section("the search worker: started and back at once, the answer later")
def _worker_blocks():
    slow = Slow()
    job = SJ.SearchJob(slow)
    check("before anything is asked: not busy, and no answer", not job.busy()
          and job.poll() is None)
    began = time.monotonic()
    started = job.ask("first")
    took = time.monotonic() - began
    check("ask() starts the search and is back at once, the call still waiting",
          started is True and took < 0.5 and not slow.gate.is_set(), (started, took))
    check("the call is made on a thread that is not the caller's",
          wait_for(slow.entered.is_set) and slow.threads[0] is not threading.current_thread())
    check("while it runs the job is busy and has no answer", job.busy() and job.poll() is None)
    check("a second ask while one runs is refused", job.ask("second") is False)
    slow.gate.set()
    answer = answer_of(job)
    check("the answer arrives later, through poll()", answer == (True, "answer to first"), answer)
    check("and only the one call was ever made", slow.calls == ["first"], slow.calls)
    check("with the answer taken the job is free", not job.busy() and job.poll() is None)
    check("and can be asked again", job.ask("third") is True
          and answer_of(job) == (True, "answer to third"))
    job.close()


@section("the search worker: a newer search makes the older answer be ignored")
def _worker_stale():
    slow = Slow()
    job = SJ.SearchJob(slow)
    job.ask("old")
    check("the old search is under way", wait_for(slow.entered.is_set))
    check("a newer question is taken while it runs",
          job.ask_again("newer") is True and job.ask_again("newest") is True)
    check("but no second call is started beside the one running", slow.calls == ["old"],
          slow.calls)
    check("and the job is still busy, with nothing to hand over", job.busy()
          and job.poll() is None)
    slow.gate.set()
    answer = answer_of(job)
    check("the newest question is the one answered", answer == (True, "answer to newest"), answer)
    check("the old answer, and the question in between, never come out",
          slow.calls == ["old", "newest"] and job.poll() is None, slow.calls)
    check("never two calls at once", slow.most == 1, slow.most)
    check("with nothing running, ask_again starts at once",
          job.ask_again("after") is True and answer_of(job) == (True, "answer to after"))
    job.close()


@section("the search worker: a failure is words, and closing ends it")
def _worker_fails():
    def broken(_what):
        raise RuntimeError("the record could not be read")

    def silent(_what):
        raise KeyError()

    bad = SJ.SearchJob(broken)
    check("a search that will fail still starts", bad.ask("x") is True)
    answer = answer_of(bad)
    check("a call that raises is an answer in words, not an exception",
          answer == (False, "the record could not be read"), answer)
    check("and the job can be asked again afterwards", not bad.busy() and bad.ask("y") is True)
    bad.close()
    quiet = SJ.SearchJob(silent)
    quiet.ask("x")
    answer = answer_of(quiet)
    check("an error with nothing to say is named by its kind",
          answer == (False, "KeyError"), answer)
    quiet.close()

    slow = Slow()
    closing = SJ.SearchJob(slow)
    closing.ask("late")
    wait_for(slow.entered.is_set)
    closing.close()
    check("closed: it says so, is not busy, and takes no new search",
          closing.closed() and not closing.busy() and closing.ask("more") is False
          and closing.ask_again("more") is False)
    slow.gate.set()
    check("the call in flight ends by itself", wait_for(lambda: not closing.running()))
    check("its answer never comes out", closing.poll() is None)
    check("and nothing was started after closing", slow.calls == ["late"], slow.calls)
    source = read("searchjob.py")
    check("the worker knows nothing of the toolkit or the window",
          "tkinter" not in source and "edsmt" not in source.replace("EDSMT", ""))
    check("its thread never keeps the program from closing", "daemon=True" in source)


# ---------------------------------------------------------------------------
# (iii) The windows, on the real toolkit
# ---------------------------------------------------------------------------

HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the window half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


POWER = "Nakato Kaine"
SYSTEMS = 132


class Reader:
    """Stands in for the read of the Powerplay record: it counts its calls,
    says which thread made each, and can be made to wait or to fail."""

    def __init__(self, real):
        self.real = real
        self.calls, self.threads = [], []
        self.gate, self.fail = None, ""
        self.entered = threading.Event()

    def __call__(self, book, origin, here=None, limit=300):
        self.calls.append(origin)
        self.threads.append(threading.current_thread())
        self.entered.set()
        gate = self.gate
        if gate is not None:
            gate.wait(30)
        if self.fail:
            raise RuntimeError(self.fail)
        return self.real(book, origin, here, limit)

    def hold(self):
        """From now on a read waits until let_go()."""
        self.gate = threading.Event()
        self.entered.clear()

    def let_go(self):
        gate, self.gate = self.gate, None
        if gate is not None:
            gate.set()


def board_answer(count, mine=""):
    """A leaderboard of `count` commanders; `mine` is added as the
    commander's own row, further down than the rows sent."""
    rows = [{"rank": n + 1, "cmdr": "CMDR %03d" % (n + 1), "power": "Li Yong-Rui",
             "pp_rank": 10, "pp_merits": 1000 * (count - n), "points": 10 * (count - n),
             "merits": 0, "finds": count - n, "far": 0, "first_bodies": 0, "verified": 0,
             "reports": 0, "layouts": 0, "confirmations": 0, "regrowth": 0}
            for n in range(count)]
    you = dict(rows[0], rank=count + 27, cmdr=mine, points=1, finds=1) if mine else None
    return {"season": "2026-11", "sort": "points", "commanders": count + 30,
            "ranked": count + 30, "week_start": "", "rows": rows, "you": you,
            "points": dict(LB.POINTS), "powers": []}


if HAVE_DISPLAY:
    import edonline as EDO    # noqa: E402

    def _offline(*_args, **_kwargs):
        raise RuntimeError("offline in tests")
    EDO.get_json = _offline
    EDO.post_json = _offline
    import overlay as OV      # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A         # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION,
                   "tour_done": True, "journal_dir": JOURNALS}, _f)
    # Copies take the Tk path everywhere, and never touch the real clipboard.
    A._windows_clipboard = lambda *args, **kwargs: False
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None
    # Anything raised inside a button or a timer lands here, not on screen.
    trouble = []
    app.report_callback_exception = lambda *args: trouble.append(args)

    def pump(seconds=0.15):
        until = time.time() + seconds
        while True:
            app.update_idletasks()
            app.update()
            if time.time() >= until:
                break
            time.sleep(0.01)

    def settle_until(cond, seconds=15.0):
        """Wait for `cond` with the window running, up to a deadline."""
        until = time.time() + seconds
        while time.time() < until:
            if cond():
                return True
            pump(0.03)
        return bool(cond())

    def poll_timers():
        """Every timer still waiting in the app that would run a Powerplay
        window's look for its answer."""
        out = []
        for job in app.tk.splitlist(app.tk.call("after", "info")):
            try:
                script = str(app.tk.splitlist(app.tk.call("after", "info", job))[0])
            except Exception:
                continue        # fired meanwhile
            if re.fullmatch(r"\d+_poll", script):
                out.append(script)
        return out

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    def texts_of(widget):
        out = []
        for child in walk(widget):
            try:
                out.append(str(child.cget("text")))
            except Exception:
                pass
        return out

    def shown(widget):
        try:
            return bool(widget.winfo_viewable())
        except Exception:
            return False

    pump()
    book = app.powerbook
    book.observe({"kind": "pledge", "power": POWER, "rank": 12, "merits": 3400,
                  "when": "2026-11-10T08:00:00Z"})
    for _n in range(SYSTEMS):
        book.observe({"kind": "system", "system": "Reach %03d" % _n,
                      "power": POWER if _n % 3 == 0 else "",
                      "state": "Fortified" if _n % 3 == 0 else "Unoccupied",
                      "powers": [POWER], "when": "2026-11-10T09:00:00Z",
                      "pos": [float(_n), 0.0, 0.0]})
    app.watcher.system = "Reach 000"
    app.watcher.star_pos = [0.0, 0.0, 0.0]
    app.watcher.cmdr = "CMDR Fifty"
    reader = Reader(A.PW.system_rows)
    A.PW.system_rows = reader
    asked = []
    app.community.leaderboard = lambda **kwargs: asked.append(kwargs) or True
    app.community.leaderboard_optin = lambda *args, **kwargs: True


def settled(win):
    """The app's own poll has had its say and no search is out."""
    app.follow_power()
    return settle_until(lambda: not win.searching())


def count_rows(win):
    return {cells[0][0]: cells[4][0] for cells in win.count_grid.rows}


@on_screen("Powerplay, Where it counts: twenty rows a page on the fast table")
def _counts_page():
    win = app.open_powerplay()
    check("the page opens saying it is searching, or already has its answer",
          win.searching() or len(win.count_grid.rows) == SYSTEMS, win.status.cget("text"))
    check("every system of the record arrives",
          settle_until(lambda: len(win.count_grid.rows) == SYSTEMS and not win.searching()),
          (len(win.count_grid.rows), win.status.cget("text")))
    grid = win.count_grid
    check("it was read on a thread that is not the window's",
          reader.threads and all(t is not threading.main_thread() for t in reader.threads),
          reader.threads)
    check("the table is the one Find and My sites use", isinstance(grid.table, A.NativeTable))
    check("it holds twenty rows, not all 132", grid.table.row_count() == 20, grid.table.row_count())
    pump(0.2)
    drawn = len(grid.table.tree.get_children())
    check("and no more than twenty are drawn", 0 < drawn <= 20, drawn)
    check("the line under it says which page of how many",
          grid.page_label.cget("text") == "Page 1 of 7 - 132 systems", grid.page_label.cget("text"))
    check("Previous and Next are on show under the table", shown(grid.previous_button)
          and shown(grid.next_button) and shown(grid.page_label))
    check("on page 1 Previous has nowhere to go and Next has",
          str(grid.previous_button.cget("state")) == "disabled"
          and str(grid.next_button.cget("state")) == "normal")
    check("the status line counts the systems listed", win.status.cget("text")
          == "132 of 132 systems listed.", win.status.cget("text"))
    ordered = [cells[0][0] for cells in grid.ordered()]
    first = [cells[0][0] for cells in grid.shown()]
    check("page 1 is the first twenty, in the order they came", first == ordered[:20], first[:3])
    check("where selling counts comes first", grid.shown()[0][4][0] in A.PW.COUNTS,
          grid.shown()[0][4])
    reads = len(reader.calls)
    grid.next_button.invoke()
    pump(0.1)
    check("Next shows page 2", grid.page_label.cget("text") == "Page 2 of 7 - 132 systems"
          and [cells[0][0] for cells in grid.shown()] == ordered[20:40],
          grid.page_label.cget("text"))
    check("drawn in the table", ordered[20] in grid.table.texts()
          and ordered[0] not in grid.table.texts(), grid.table.texts()[:8])
    check("and now Previous can go back", str(grid.previous_button.cget("state")) == "normal")
    for _ in range(9):
        grid.next_button.invoke()
    pump(0.1)
    check("Next stops at the last page, which holds the 12 left over",
          grid.page_label.cget("text") == "Page 7 of 7 - 132 systems"
          and grid.table.row_count() == 12
          and str(grid.next_button.cget("state")) == "disabled", grid.page_label.cget("text"))
    grid.previous_button.invoke()
    pump(0.1)
    check("Previous goes back one", grid.page_label.cget("text") == "Page 6 of 7 - 132 systems")
    check("turning pages never read the record again", len(reader.calls) == reads,
          (reads, len(reader.calls)))
    grid.table._sorted(A.SYSTEM_HEADERS.index("System"))
    pump(0.1)
    check("a click on a heading sorts every row, not just the page, and goes to page 1",
          grid.page_label.cget("text") == "Page 1 of 7 - 132 systems"
          and [cells[0][0] for cells in grid.shown()] == sorted(ordered)[:20],
          [cells[0][0] for cells in grid.shown()][:3])
    check("the heading says which way", "System ^" in grid.table.texts(), grid.table.texts()[:6])
    check("and sorting did not read the record either", len(reader.calls) == reads)
    block = grid.as_text()
    check("Copy all still takes every page", len(block.splitlines()) == SYSTEMS + 1,
          len(block.splitlines()))
    why = A.SYSTEM_HEADERS.index("Why")
    shown_text, whole = grid.table.cell_text(0, why)
    check("a Why cell shows the few words, and its tip and its copy the sentence",
          len(whole) > len(shown_text) and whole in block, (shown_text, whole))
    grid.next_button.invoke()
    win.only_counts.set(True)
    win.only_changed()
    pump(0.1)
    counting = [cells for cells in grid.rows if cells[4][0] in A.PW.COUNTS]
    check("Only where it counts is a changed filter: page 1, and only those rows",
          len(grid.rows) == len(counting) == 15 and grid.page == 0, (len(grid.rows), grid.page))
    check("fifteen rows are one page, so there is nothing to turn",
          not shown(grid.previous_button) and not shown(grid.next_button))
    check("it hid rows already in hand, without another read", len(reader.calls) == reads)
    win.only_counts.set(False)
    win.only_changed()
    pump(0.1)
    grid.next_button.invoke()
    grid.next_button.invoke()
    check("on page 3 before a filter changes", grid.page == 2, grid.page)
    A.set_entry(win.mined_box, "Reach 003")
    typed = win.mined_box._entry        # the toolkit's entry holds the real one
    typed.focus_force()
    pump(0.05)
    typed.event_generate("<KeyRelease>", keysym="3")
    check("typing in Mined in is a new search", settle_until(
        lambda: len(reader.calls) > reads and not win.searching()), reader.calls[-3:])
    check("for the system typed", reader.calls[-1] == "Reach 003", reader.calls[-1])
    check("and its answer starts on page 1", grid.page == 0
          and count_rows(win).get("Reach 003") == "Reinforce", count_rows(win).get("Reach 003"))
    A.set_entry(win.mined_box, "")
    win.repaint()
    settle_until(lambda: not win.searching())
    grid.next_button.invoke()
    reads = len(reader.calls)
    book.observe({"kind": "system", "system": "Reach 999", "power": "", "state": "Unoccupied",
                  "powers": [POWER], "when": "2026-11-10T10:00:00Z", "pos": [999.0, 0.0, 0.0]})
    app.follow_power()
    check("a change to the record is searched for by itself", settle_until(
        lambda: len(grid.rows) == SYSTEMS + 1 and not win.searching()), len(grid.rows))
    check("and leaves the page being read where it was", grid.page == 1
          and grid.page_label.cget("text") == "Page 2 of 7 - 133 systems",
          grid.page_label.cget("text"))
    check("nothing was raised into the window", not trouble, trouble)


@on_screen("Powerplay: a search that takes its time does not hold the window")
def _counts_search():
    win = app.power_window
    grid = win.count_grid
    settled(win)
    reads = len(reader.calls)
    reader.hold()
    began = time.monotonic()
    started = win.refresh()
    took = time.monotonic() - began
    check("Refresh starts the search and is back at once", started is True and took < 0.5, took)
    check("the page says it is searching", win.searching()
          and win.status.cget("text").startswith("Searching"), win.status.cget("text"))
    check("the read is under way on its own thread", settle_until(reader.entered.is_set)
          and reader.threads[-1] is not threading.main_thread())
    fired = []
    app.after(1, lambda: fired.append(True))
    check("the window goes on working while the read waits", settle_until(lambda: bool(fired))
          and win.searching())
    check("what was on show stays on show meanwhile", grid.table.row_count() == 20)
    again = win.refresh()
    win.refresh_button.invoke()
    pump(0.2)
    check("Refresh again while one runs does not start another",
          again is False and len(reader.calls) == reads + 1, (again, len(reader.calls) - reads))
    reader.let_go()
    check("the answer arrives later and is drawn", settle_until(lambda: not win.searching())
          and win.status.cget("text") == "133 of 133 systems listed.", win.status.cget("text"))
    check("with one read for all of it", len(reader.calls) == reads + 1)

    # A newer search while an older one is still out.
    drawn = []
    real_show = grid.show
    grid.show = lambda *args, **kwargs: drawn.append(args[1]) or real_show(*args, **kwargs)
    try:
        reads = len(reader.calls)
        reader.hold()
        win.refresh()
        settle_until(reader.entered.is_set)
        A.set_entry(win.mined_box, "Reach 003")
        win.repaint()
        pump(0.2)
        check("a changed box while a search is out waits its turn", win.searching()
              and len(reader.calls) == reads + 1, len(reader.calls) - reads)
        reader.let_go()
        check("both reads are made, one after the other", settle_until(
            lambda: not win.searching()) and reader.calls[reads:] == ["Reach 000", "Reach 003"],
            reader.calls[reads:])
        check("only the newer answer is drawn - the older one is ignored",
              len(drawn) == 1 and count_rows(win).get("Reach 003") == "Reinforce"
              and count_rows(win).get("Reach 000") == "Nothing",
              (len(drawn), count_rows(win).get("Reach 000")))
    finally:
        grid.show = real_show
        A.set_entry(win.mined_box, "")
    win.repaint()
    settle_until(lambda: not win.searching())

    # A read that fails.
    before = count_rows(win)
    reader.fail = "the record is locked"
    try:
        win.refresh()
        check("a failed search ends", settle_until(lambda: not win.searching()))
    finally:
        reader.fail = ""
    said = win.status.cget("text")
    check("and is said in plain words on the page", said.startswith("Could not")
          and "the record is locked" in said, said)
    check("in the colour of a fault", str(win.status.cget("text_color")) == str(A.RED))
    check("what was on show is kept", count_rows(win) == before and grid.table.row_count() == 20)
    check("nothing was raised into the window", not trouble, trouble)
    check("and Refresh works again afterwards", win.refresh() is True
          and settle_until(lambda: not win.searching())
          and win.status.cget("text") == "133 of 133 systems listed.", win.status.cget("text"))


@on_screen("Powerplay, Where to sell: the same table, a page at a time")
def _sell_page():
    win = app.power_window
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 600))
    names = ["Platinum", "Gold", "Silver", "Osmium", "Palladium", "Painite"]
    app.hold_now = lambda: {name: 10 + n for n, name in enumerate(names)}
    app.sell_quotes = {name.lower(): {"commodity": name, "at": time.time(), "rows": [
        {"commodity": name, "station": "%s Port %d" % (name, n), "system": "Reach %03d" % n,
         "sell": 100000 + 1000 * n, "demand": 500, "distance_ly": float(n), "pad": "L",
         "station_type": "Coriolis", "seen": stamp} for n in range(6)]}
        for name in names[:5]}
    reads = len(reader.calls)
    win.show_page(1)
    pump(0.2)
    grid = win.sell_grid
    check("the table is the one Find and My sites use", isinstance(grid.table, A.NativeTable))
    check("five payers for each of five commodities, and a line for the one with no price",
          len(grid.rows) == 26 and grid.rows[-1][2][0].startswith("no price known"),
          len(grid.rows))
    check("twenty of them on page 1", grid.table.row_count() == 20
          and grid.page_label.cget("text") == "Page 1 of 2 - 26 rows", grid.page_label.cget("text"))
    grid.next_button.invoke()
    pump(0.1)
    check("Next shows the other six, the unpriced line last", grid.table.row_count() == 6
          and grid.shown()[-1][2][0].startswith("no price known")
          and grid.page_label.cget("text") == "Page 2 of 2 - 26 rows", grid.page_label.cget("text"))
    win.order_box.suggest.pick("Nearest")
    pump(0.2)
    check("a changed Order goes back to page 1", grid.page == 0
          and grid.page_label.cget("text") == "Page 1 of 2 - 26 rows")
    win.copy_all()
    check("Copy all takes both pages", win.status.cget("text").startswith("Copied 26 row(s)"),
          win.status.cget("text")[:40])
    win.show_page(0)
    check("back on Where it counts the record is searched again, off the window's thread",
          settle_until(lambda: len(reader.calls) > reads and not win.searching())
          and reader.threads[-1] is not threading.main_thread())
    del app.hold_now
    settled(win)
    check("nothing was raised into the window", not trouble, trouble)


@on_screen("Powerplay: closing the window or its tab stops the search and the looking")
def _closing():
    win = app.power_window
    job = win._search
    settled(win)
    reader.hold()
    win.refresh()
    settle_until(reader.entered.is_set)
    check("while a search is out the window looks for its answer",
          win._poll_job is not None and len(poll_timers()) == 1, poll_timers())
    win.destroy()
    pump(0.1)
    check("closing the tab ends the search", job.closed() and not job.busy())
    check("and stops the looking: no timer of the window's is left",
          win._poll_job is None and not poll_timers(), poll_timers())
    reader.let_go()
    check("the read still out ends by itself", wait_for(lambda: not job.running()))
    pump(0.3)
    check("its answer goes nowhere", job.poll() is None)
    app.follow_power()
    check("and the app carries on without the window", not trouble, trouble)

    # The same, as a window of its own.
    app.settings["tools_as_tabs"] = False
    try:
        win = app.open_powerplay()
        check("opened as a window of its own", not win.docked)
        settled(win)
        job = win._search
        reader.hold()
        win.refresh()
        settle_until(reader.entered.is_set)
        win._shell._close()
        pump(0.1)
        check("closing the window ends the search and the looking",
              job.closed() and not poll_timers(), poll_timers())
        reader.let_go()
        wait_for(lambda: not job.running())
        pump(0.3)
        check("with nothing raised", not trouble, trouble)
    finally:
        reader.let_go()
        app.settings["tools_as_tabs"] = True


@on_screen("the Leaderboard: the same table, twenty a page, everything else as it was")
def _leaderboard():
    win = app.open_leaderboard()
    pump(0.2)
    check("opening it asks the community map once", len(asked) == 1
          and asked[0].get("tag") == A.LB_TAG and asked[0].get("limit") == LB.ROW_LIMIT, asked)
    app.take_board(A.LB_TAG, True, json.dumps(board_answer(50, mine="CMDR Fifty")))
    pump(0.2)
    grid = win.grid_table
    table = grid.table
    check("the table is the one Find and My sites use", isinstance(table, A.NativeTable))
    check("fifty commanders and your own row are all in hand", len(grid.rows) == 51, len(grid.rows))
    check("twenty of them on page 1", table.row_count() == 20
          and 0 < len(table.tree.get_children()) <= 20, table.row_count())
    check("the line under it counts commanders",
          grid.page_label.cget("text") == "Page 1 of 3 - 51 commanders", grid.page_label.cget("text"))
    check("number 1 leads page 1", grid.shown()[0][1][0] == "CMDR 001", grid.shown()[0][1])
    grid.next_button.invoke()
    grid.next_button.invoke()
    pump(0.1)
    check("page 3 holds the last eleven", table.row_count() == 11
          and grid.page_label.cget("text") == "Page 3 of 3 - 51 commanders",
          grid.page_label.cget("text"))
    check("turning pages never asked the community map again", len(asked) == 1, len(asked))
    check("your own row is the last, as before", grid.shown()[-1][1][0] == "CMDR Fifty"
          and grid.shown()[-1][1][1] == A.ORANGE)
    check("and it is marked as yours in the table", table.row_tone(10) == "own"
          and table.row_tone(9) == "", (table.row_tone(10), table.row_tone(9)))
    item = table.tree.get_children()[10]
    check("in the accent colour", "own" in table.tree.item(item, "tags")
          and str(table.tree.tag_configure("own", "foreground")) == str(A.ORANGE),
          table.tree.item(item, "tags"))
    table._sorted(LB.HEADERS.index("Finds"))
    pump(0.1)
    check("a click on a heading sorts every row and goes to page 1", grid.page == 0
          and grid.shown()[0][1][0] in ("CMDR 050", "CMDR Fifty"), grid.shown()[0][1])
    check("without asking again", len(asked) == 1)
    block = grid.as_text()
    check("Copy all takes every page", len(block.splitlines()) == 52
          and block.splitlines()[0].startswith("Rank | Commander | Power"), len(block.splitlines()))
    labels = texts_of(win)
    check("the seasons, the views, Refresh, Join or Leave, Share my week and On the web "
          "are all still there",
          all(name in labels for name, _key in LB.SEASONS + LB.VIEWS)
          and all(name in labels for name in ("Refresh", "Leave", "Share my week",
                                              "On the web", "Copy all")),
          [n for n in ("Refresh", "Leave", "Share my week", "On the web") if n not in labels])
    check("your place is still said above the table", "CMDR Fifty" in win.you.cget("text"),
          win.you.cget("text"))
    win.pick("All time")
    check("another season asks again - that is a new search", len(asked) == 2
          and asked[-1].get("season") == "all", asked[-1:])
    app.take_board(A.LB_TAG, True, json.dumps(board_answer(12)))
    pump(0.2)
    check("twelve commanders are one page: all twelve, and nothing to turn",
          table.row_count() == 12 and not shown(grid.previous_button)
          and not shown(grid.next_button), table.row_count())
    app.take_board(A.LB_TAG, True, json.dumps(board_answer(0)))
    pump(0.2)
    check("an empty board says how points come, in the table's place",
          grid.rows == [] and "Nobody has points" in table.advice.cget("text")
          and shown(table.advice), table.advice.cget("text")[:40])
    check("nothing was raised into the window", not trouble, trouble)
    win.destroy()
    pump(0.1)


# ---------------------------------------------------------------------------
# (iv) What the source no longer does, and what the guide says
# ---------------------------------------------------------------------------

@on_screen("none of the three tables is a grid of a widget a cell any more")
def _source():
    for name in ("PowerplayWindow", "LeaderboardWindow", "PagedTable"):
        source = inspect.getsource(getattr(A, name))
        slow = [word for word in ("ScrollTable(", "cell_label(", "row_buttons(", "CTkLabel(self.table",
                                  ".inner", "CTkScrollableFrame(") if word in source]
        check("%s builds no label grid" % name, not slow, slow)
    check("the old grid class is gone", not hasattr(A, "GridTable"))
    paged = inspect.getsource(A.PagedTable)
    check("the paged table draws on the tree view, a page of rows at a time",
          "NativeTable(" in paged and "TV.page_rows(" in paged)
    power = inspect.getsource(A.PowerplayWindow)
    check("the Powerplay page reads its rows through the search worker, never in a button",
          "SJ.SearchJob(" in power and "PW.system_rows(" in inspect.getsource(
              A.PowerplayWindow._read_counts)
          and power.count("PW.system_rows(") == 1, power.count("PW.system_rows("))
    check("and looks for the answer with a timer it cancels when it closes",
          "self.after(POWER_POLL_MS" in power and "after_cancel" in power)
    for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
        check("the search worker is packed into %s" % spec,
              '"searchjob"' in read("build", spec))


@section("the guide and the list of checks")
def _documents():
    guide = " ".join(read("docs", "GUIDE.md").split())
    check("the guide says the Powerplay tab's tables are twenty rows a page",
          "**Where it counts**" in guide and "twenty rows a page" in guide)
    check("that the search no longer holds the window",
          "without holding the window" in guide)
    check("and that the Leaderboard turns pages too",
          "Previous** and **Next**" in guide.split("### The leaderboard")[1].split("###")[0])
    check("this file is run with the rest", "test_110042_powerplay.py" in read("tests", "run_all.py"))


if HAVE_DISPLAY:
    try:
        app.destroy()
    except Exception:
        pass

print("\n%d failure(s)" % len(fails) if fails else "\nFAILURES: 0")
sys.exit(1 if fails else 0)
