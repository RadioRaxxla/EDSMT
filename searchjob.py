"""A search run off the window's thread (1.10042).

The Powerplay tool read its record and drew the answer on the window's own
thread, so the window stood still until both were done. A SearchJob makes
the call on a thread of its own and keeps the answer until the window asks
for it:

    job = SearchJob(call)
    job.ask(...)        start a search and come straight back; refused
                        while one is out
    job.ask_again(...)  what is wanted has changed: the search that is out
                        no longer counts, and this one is run in its place
    job.poll()          None, or (True, what the call returned), or
                        (False, what went wrong, in words)
    job.close()         the window has gone: no more answers

One call runs at a time, however often it is asked. Only the answer to the
newest question ever comes out of poll(); an older one is thrown away.

Nothing here touches a widget: the window looks for the answer from a timer
of its own. Never raises.
"""
import queue
import threading


def words(exc):
    """What went wrong, to be said on the page: the error's own words, or
    its kind when it has none."""
    return str(exc).strip() or type(exc).__name__


class SearchJob:
    """`call` is made with whatever ask() or ask_again() is given, never on
    the thread that asked."""

    def __init__(self, call, name="EDSMT search"):
        self._call = call
        self._name = name
        self._lock = threading.Lock()
        self._answers = queue.Queue()
        self._ticket = 0          # the newest question asked
        self._awaited = None      # its ticket, until its answer is taken
        self._next = None         # what to run when the call that is out returns
        self._running = False     # a call is out on the thread
        self._closed = False

    # -- asking ------------------------------------------------------------

    def ask(self, *args, **kwargs):
        """Start a search and come straight back. False - and nothing is
        started - while one is out, or after close()."""
        with self._lock:
            if self._closed or self._awaited is not None:
                return False
            return self._begin(args, kwargs)

    def ask_again(self, *args, **kwargs):
        """What is wanted has changed. The answer to a search still out is
        thrown away when it comes, and this one is run in its place: at once
        when nothing is running, otherwise as soon as the call that is out
        returns - never beside it. Asked several times meanwhile, only the
        last is run. False only after close()."""
        with self._lock:
            if self._closed:
                return False
            return self._begin(args, kwargs)

    def _begin(self, args, kwargs):
        # The lock is held.
        self._ticket += 1
        self._awaited = self._ticket
        work = (self._ticket, args, kwargs)
        if self._running:
            self._next = work
            return True
        self._running = True
        try:
            threading.Thread(target=self._run, args=(work,), name=self._name,
                             daemon=True).start()
        except RuntimeError as exc:
            # No thread to be had: that is the answer, in words.
            self._running = False
            self._answers.put((self._ticket, False, words(exc)))
        return True

    def _run(self, work):
        while True:
            ticket, args, kwargs = work
            try:
                answer = (ticket, True, self._call(*args, **kwargs))
            except Exception as exc:    # noqa: BLE001 - said in words by whoever asked
                answer = (ticket, False, words(exc))
            with self._lock:
                self._answers.put(answer)
                work, self._next = self._next, None
                if work is None or self._closed:
                    self._running = False
                    return

    # -- the answer ----------------------------------------------------------

    def poll(self):
        """The newest question's answer if it is in - (True, value) or
        (False, words) - and None if it is not. Each answer comes out once."""
        found = None
        with self._lock:
            while True:
                try:
                    ticket, ok, value = self._answers.get_nowait()
                except queue.Empty:
                    break
                if ticket == self._awaited and not self._closed:
                    found = (ok, value)
                    self._awaited = None
        return found

    def busy(self):
        """A question has been asked and its answer has not been taken."""
        with self._lock:
            return self._awaited is not None

    def running(self):
        """A call is still out on the thread - even one whose answer no
        longer counts."""
        with self._lock:
            return self._running

    def closed(self):
        return self._closed

    def close(self):
        """No more answers, and nothing new is started. A call still out
        ends by itself and its answer is thrown away."""
        with self._lock:
            self._closed = True
            self._awaited = None
            self._next = None
