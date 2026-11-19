"""1.10042: "What did it say?" - the last 50 spoken lines, with their time.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_voicehistory.py
"""
import faulthandler
import io
import os
import sys
import tempfile
import time

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-vh42-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import voice as VO   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


class Sink:
    def __init__(self):
        self.written = []
        self.stdin = self
        self.stderr = None

    def write(self, data):
        self.written.append(data)

    def flush(self):
        pass

    def poll(self):
        return None

    def kill(self):
        pass

    def close(self):
        pass


def wait_for(test, seconds=5.0):
    end = time.time() + seconds
    while time.time() < end:
        if test():
            return True
        time.sleep(0.02)
    return test()


print("== the speaker keeps what it said ==")
speaker = VO.Speaker(spawn=Sink)
check("nothing said, nothing kept", speaker.history() == [])
speaker.say_line("online", "flight_controller")
speaker.say_text("Platinum, 340 metres, two o'clock")
words = [w for _t, w in speaker.history()]
check("newest first", words[0] == "Platinum, 340 metres, two o'clock" and "online" in words[1].lower(), words)
check("each with its time", all(abs(t - time.time()) < 30 for t, _w in speaker.history()))
check("a line given as words is noted once", len(words) == 2, words)
big = VO.Speaker(spawn=Sink)
for n in range(70):
    big.say_text("line number %d" % n)
    wait_for(lambda: big._queue.empty(), 5)
check("only the last 50", len(big.history()) == 50 and big.history()[0][1] == "line number 69"
      and big.history()[-1][1] == "line number 20", (len(big.history()), big.history()[-1:]))
# A speaker that cannot speak, on any system: with no spawn given, Windows
# supplies its own and the line would really be spoken (seen on the PC).
none = VO.Speaker(spawn=Sink)
none.closed = True
none.say_text("never heard")
check("a line that cannot be said is not recorded", none.history() == [])
rows = VO.history_rows([(time.mktime((2026, 11, 18, 9, 5, 7, 0, 0, -1)), "Deposit logged.")])
check("the window's rows read HH:MM:SS then the words", rows == [("09:05:07", "Deposit logged.")], rows)
check("a bad time is skipped, not a crash", VO.history_rows([("x", "a"), (None, "b")]) == [])
check("one place records it: _send", "self._said.append" in read("voice.py")
      and read("voice.py").count("self._said.append") == 1)

print("== wiring ==")
src = read("edsmt.py")
check("Help has What did it say?", "What did it say? - the last spoken lines" in src and "def open_voice_history" in src)
check("so does Settings > Voice", 'text="What did it say?"' in src and "class VoiceHistoryWindow" in src)
check("the guide says it", "what did it say?" in read("docs", "GUIDE.md").lower())
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
