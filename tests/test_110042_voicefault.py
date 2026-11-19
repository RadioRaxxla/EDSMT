"""1.10042: a voice that cannot speak says why.

Reported from other players' PCs: Test voice said "Speaking" and nothing
was heard, and nothing anywhere said what was wrong. Every failure was
swallowed: the speech process kept its errors to itself, a process that
would not start was simply not started, and Test voice reported success
the moment the line was queued.

Now the speech process reports what failed, the speaker keeps the newest
problem in plain words, the app says it once on the status bar, and Test
voice waits for the result before it says anything went well.

    python tests/test_110042_voicefault.py
"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import voice as VO      # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="edsmt-voicefault-")


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def wait_for(test, seconds=6.0):
    """Wait for a result, never a fixed number of loops."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.02)
    return bool(test())


print("== the speech process no longer keeps its errors to itself ==")
script = VO.SPEECH_SCRIPT
check("no failure is swallowed in silence", "catch { }" not in script)
check("a line that fails is reported with what kind of line it was",
      "[Console]::Error.WriteLine('E ' + $what + ' '" in script, script)
check("speech that cannot be set up is reported, and recordings still play without it",
      "[Console]::Error.WriteLine('E ! '" in script and "$voice = $null" in script and "exit" not in script)
check("the script is still handed over whole", VO.powershell_command()[-2] == "-EncodedCommand")
check("the reason reported is the one nearest the fault, not the wrapper round it",
      "InnerException" in script and "(Why $_)" in script)
check("PowerShell's own progress records are switched off", "$ProgressPreference = 'SilentlyContinue'" in script)

print("== what a report means, in plain words ==")
check("a recording", VO.explain_problem("E W Could not find file 'C:\\x\\online.wav'.").startswith(
    "A recording could not be played"), VO.explain_problem("E W Could not find file 'C:\\x\\online.wav'."))
check("a spoken line", VO.explain_problem("E S No voice installed").startswith("Windows could not speak the line"))
check("speech itself", VO.explain_problem("E ! Could not load System.Speech").startswith(
    "Windows' speech could not be started"))
check("the reason is kept", "No voice installed" in VO.explain_problem("E S No voice installed"))
check("anything else is passed on as it came, one line, not too long",
      VO.explain_problem("odd\nthing " + "x" * 500).startswith("odd thing")
      and len(VO.explain_problem("odd\nthing " + "x" * 500)) <= 220)
check("nothing is nothing", VO.explain_problem("") == "" and VO.explain_problem(None) == "")

STANDIN = os.path.join(TMP, "standin.py")
with open(STANDIN, "w", encoding="utf-8") as fh:
    fh.write("import sys\n"
             "mode = sys.argv[1]\n"
             "if mode == 'dead':\n"
             "    sys.stderr.write('E ! Could not load System.Speech\\n'); sys.stderr.flush(); sys.exit(3)\n"
             "while True:\n"
             "    line = sys.stdin.buffer.readline()\n"
             "    if not line:\n"
             "        break\n"
             "    text = line.decode('utf-8').rstrip('\\n')\n"
             "    if mode == 'noise':\n"
             "        sys.stderr.write('#< CLIXML\\n<Objs Version=\"1.1.0.1\"><Obj S=\"progress\"></Obj></Objs>\\n'); sys.stderr.flush()\n"
             "    if mode == 'nowav' and text.startswith('W '):\n"
             "        sys.stderr.write(\"E W Could not find file '\" + text[2:] + \"'.\\n\"); sys.stderr.flush()\n")


def spawner(mode, pipe=True):
    started = []

    def spawn():
        proc = subprocess.Popen([sys.executable, "-u", STANDIN, mode], stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE if pipe else None)
        started.append(proc)
        return proc
    spawn.started = started
    return spawn


print("== the speaker keeps the newest problem ==")
quiet = VO.Speaker(spawn=spawner("ok"))
check("with nothing wrong there is no problem", quiet.problem() == "")
quiet.say_text("Rig one down.")
check("and still none after a line that worked", wait_for(lambda: quiet.sent >= 1) and quiet.problem() == "",
      quiet.problem())
quiet.close()

before = time.time()
missing = VO.Speaker(spawn=spawner("nowav"))
missing._send("W " + os.path.join(TMP, "online.wav"))
check("a recording that will not play is known within moments",
      wait_for(lambda: missing.problem() != ""), missing.problem())
check("in plain words, with the reason", missing.problem().startswith("A recording could not be played")
      and "online.wav" in missing.problem(), missing.problem())
check("asked for problems since now, an old one is not news", missing.problem(since=time.time() + 1) == "")
check("asked since before it happened, it is", missing.problem(since=before) != "")
missing.close()


def refuses():
    raise OSError("blocked by policy")


blocked = VO.Speaker(spawn=refuses)
blocked.say_text("Online.")
check("a speech process that will not start is a problem, not a silence",
      wait_for(lambda: "could not be started" in blocked.problem()) and "blocked by policy" in blocked.problem(),
      blocked.problem())
blocked.close()

dead_spawn = spawner("dead")
dead = VO.Speaker(spawn=dead_spawn)
dead.say_text("Online.")
check("one that dies as it starts says what it said on the way out",
      wait_for(lambda: "System.Speech" in dead.problem()), dead.problem())
for _ in range(VO.MAX_STARTS + 2):
    dead.say_text("Online.")
    time.sleep(0.3)
check("it is not started for ever", wait_for(lambda: len(dead_spawn.started) == VO.MAX_STARTS, 4.0)
      and len(dead_spawn.started) == VO.MAX_STARTS, len(dead_spawn.started))
dead.close()

# Seen on a real PC: Windows PowerShell writes "#< CLIXML" and a progress
# record to the error stream of a process whose errors are being read.
noisy_spawn = spawner("noise")
noisy = VO.Speaker(spawn=noisy_spawn)
noisy.say_text("Online.")
noisy.say_text("Rig one down.")
check("what PowerShell itself writes on the error stream is not a problem",
      wait_for(lambda: noisy.sent >= 2) and not wait_for(lambda: noisy.problem() != "", 1.0), noisy.problem())
noisy.close()

old_style = VO.Speaker(spawn=spawner("ok", pipe=False))
old_style.say_text("Online.")
check("a process with nothing to read errors from still speaks", wait_for(lambda: old_style.sent >= 1)
      and old_style.problem() == "", old_style.problem())
old_style.close()

print("== Test voice waits for the result ==")
check("heard nothing wrong: it says so", VO.test_report("", "Rig one down.", "Celestia", "normal")
      == ("Spoken: \"Rig one down.\" (Celestia, normal). If you heard nothing, check the sound device "
          "Windows is playing to.", "ok"), VO.test_report("", "Rig one down.", "Celestia", "normal"))
told = VO.test_report("A recording could not be played: missing.", "Rig one down.", "Celestia", "normal")
check("something went wrong: it says what, and that it is not the commander's doing",
      told[1] == "bad" and "A recording could not be played: missing." in told[0]
      and told[0].startswith("The voice could not speak"), told)
check("the wait is long enough for a process to start and fail", 1.0 <= VO.TEST_WAIT_S <= 4.0)

source = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
test_voice = source.split("    def test_voice(self):")[1].split("\n    def ")[0]
check("Test voice no longer reports success the moment the line is queued",
      'self.say("Speaking: ' not in test_voice and "voice_test_result" in test_voice, test_voice[:300])
check("it comes back for the result", "def voice_test_result" in source and "VO.test_report(" in source)

print("== in use, a problem is said once ==")
speak = source.split("    def speak(self, line_id, force=False, theme=None, rate=None):")[1].split("\n    def ")[0]
check("the app asks the speaker whether anything went wrong", "voice_trouble(" in speak or "voice_trouble(" in source)
check("and says it on the status bar", "def voice_trouble" in source)

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
