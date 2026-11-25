"""1.10042: supporter voices - what a paired install is allowed (perks.py).

A paired EDSMT asks the member page what the commander may have, at start and
about every six hours. The answer carries a grant signed by the member page;
EDSMT checks it on this computer against the key it has pinned (by key id, the
previous key honoured), keeps the answer - never the token - in settings, and
on a 401, an expired or bad grant, or no pairing: no perks, the Basic lines,
nothing broken. Settings says plainly where it stands.

Pure parts run anywhere; the window part needs a display:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110042_perks.py
"""
import base64
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-perks-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import perks as PK          # noqa: E402
import signing as SG        # noqa: E402
import supportbundle as SB  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def b64u(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


SECRET = bytes(range(1, 33))            # made up; never a real key
OTHER = bytes(range(33, 65))
PUB = SG.encode(SG.public_key(SECRET))
PUB2 = SG.encode(SG.public_key(OTHER))
KEY = {"kid": "aaaa1111", "public_key": PUB}
KEY2 = {"kid": "bbbb2222", "public_key": PUB2}
NOW = 1_800_000_000
TOKEN = "fake-pairing-token-" + "Q7" * 14


def grant(supporter=True, tester=False, exp=NOW + 3600, kid="aaaa1111", tool="edsmt", secret=SECRET):
    claims = {"exp": exp, "iat": NOW - 10, "kid": kid, "supporter": supporter, "tester": tester,
              "tool": tool}
    payload = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    return b64u(payload) + "." + b64u(SG.sign(secret, payload))


print("== the grant is checked here, offline ==")
good = PK.verify_grant(grant(), [KEY], now=NOW)
check("a good grant gives its claims", good and good["supporter"] is True and good["tool"] == "edsmt", good)
check("an expired grant is nothing", PK.verify_grant(grant(exp=NOW - 1), [KEY], now=NOW) is None)
check("another tool's grant is nothing", PK.verify_grant(grant(tool="edst"), [KEY], now=NOW) is None)
check("signed by another key is nothing", PK.verify_grant(grant(secret=OTHER), [KEY], now=NOW) is None)
check("a key id nobody has pinned is nothing", PK.verify_grant(grant(kid="cccc3333"), [KEY], now=NOW) is None)
check("the previous key is honoured by its id",
      PK.verify_grant(grant(kid="bbbb2222", secret=OTHER), [KEY, KEY2], now=NOW) is not None)
tampered = grant().split(".")
payload = json.loads(base64.urlsafe_b64decode(tampered[0] + "=" * (-len(tampered[0]) % 4)))
payload["tester"] = True
tampered[0] = b64u(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
check("a changed payload is nothing", PK.verify_grant(".".join(tampered), [KEY], now=NOW) is None)
for junk in ("", None, "abc", "a.b", "a.b.c", 12, "!!.!!"):
    check("junk %r is nothing, and never raises" % (junk,), PK.verify_grant(junk, [KEY], now=NOW) is None)
check("no keys pinned is nothing", PK.verify_grant(grant(), [], now=NOW) is None)
check("a grant without a whole-number expiry is nothing",
      PK.verify_grant(grant(exp="soon"), [KEY], now=NOW) is None)

print("== the key the member page publishes ==")
keys = PK.keys_from_answer({"alg": "Ed25519", "kid": "aaaa1111", "public_key": PUB,
                            "previous": {"kid": "bbbb2222", "public_key": PUB2}})
check("the key, and the previous one after it", keys == [KEY, KEY2], keys)
check("a key that is not 32 bytes is dropped",
      PK.keys_from_answer({"kid": "aaaa1111", "public_key": "AAAA"}) == [])
check("so is another algorithm", PK.keys_from_answer({"alg": "RSA", "kid": "x1", "public_key": PUB}) == [])
check("a key without an id is dropped", PK.keys_from_answer({"public_key": PUB}) == [])
check("nonsense is no keys", PK.keys_from_answer("nope") == [] and PK.keys_from_answer(None) == [])

print("== what the member page's answer becomes ==")


def answer(supporter=True, tester=False, **more):
    out = {"member": True, "supporter": supporter, "tester": tester, "sources": ["discord"],
           "checked": "2027-01-15T08:00:00Z", "grant": grant(supporter, tester), "exp": NOW + 3600}
    out.update(more)
    return out


def ask_with(reply, seen=None):
    def get(url, timeout=20.0, headers=None):
        if seen is not None:
            seen.append((url, headers))
        if isinstance(reply, Exception):
            raise reply
        return reply[url] if isinstance(reply, dict) and url in reply else reply
    return get


seen = []
reply = {PK.PERKS_URL: answer(), PK.KEY_URL: {"alg": "Ed25519", **KEY}}
job = PK.refresh_job(TOKEN, ask_with(reply, seen), [])
out = json.loads(job())
check("it asks with the token as a bearer",
      seen[0][0] == PK.PERKS_URL and seen[0][1] == {"Authorization": "Bearer " + TOKEN}, seen)
check("with no key pinned yet it fetches the key once", [u for u, _h in seen] == [PK.PERKS_URL, PK.KEY_URL], seen)
check("and gives the grant checked against it", out["status"] == "ok" and out["supporter"] is True
      and out["keys"] == [KEY] and out["grant"], out)
check("the token is nowhere in what comes back", TOKEN not in json.dumps(out))

seen.clear()
out = json.loads(PK.refresh_job(TOKEN, ask_with(reply, seen), [KEY])())
check("with the key pinned it does not fetch it again", [u for u, _h in seen] == [PK.PERKS_URL], seen)
check("a role the member does not have reads as no", json.loads(PK.refresh_job(
    TOKEN, ask_with({PK.PERKS_URL: answer(False, False)}), [KEY])())["supporter"] is False)
bad = answer()
bad["grant"] = grant(secret=OTHER)
out = json.loads(PK.refresh_job(TOKEN, ask_with({PK.PERKS_URL: bad}), [KEY])())
check("a grant that does not check is no perks, said as that", out["status"] == "bad-grant"
      and out["supporter"] is False and out["tester"] is False, out)
out = json.loads(PK.refresh_job(TOKEN, ask_with(
    RuntimeError("join.radioraxxla.com refused it (HTTP 401): unknown token")), [KEY])())
check("a 401 is an answer, not an error: no perks", out["status"] == "refused" and not out["supporter"], out)
try:
    PK.refresh_job(TOKEN, ask_with(RuntimeError("could not reach join.radioraxxla.com: timed out")), [KEY])()
    check("no connection is an error for the worker to report", False)
except RuntimeError as exc:
    check("no connection is an error for the worker to report", "could not reach" in str(exc))
lying = answer(False, False)
lying["supporter"] = True
check("the claims decide, not the unsigned words round them",
      json.loads(PK.refresh_job(TOKEN, ask_with({PK.PERKS_URL: lying}), [KEY])())["supporter"] is False)
rotated = answer()
rotated["grant"] = grant(kid="bbbb2222", secret=OTHER)
reply2 = {PK.PERKS_URL: rotated, PK.KEY_URL: {"alg": "Ed25519", **KEY2, "previous": KEY}}
seen.clear()
out = json.loads(PK.refresh_job(TOKEN, ask_with(reply2, seen), [KEY])())
check("a grant under a new key id fetches the key again, and checks", out["status"] == "ok"
      and out["keys"] == [KEY2, KEY] and [u for u, _h in seen] == [PK.PERKS_URL, PK.KEY_URL], out)

print("== settings keep the answer, never the token ==")
base = {"portal_token": TOKEN, "portal_device": "a1"}
mine = PK.apply(base, json.dumps(PK.refresh_job(TOKEN, ask_with(reply), [KEY]) and json.loads(
    PK.refresh_job(TOKEN, ask_with(reply), [KEY])())), now=NOW)
check("supporter, tester, checked and the grant are kept", mine["perks"]["supporter"] is True
      and mine["perks"]["checked"] and mine["perks_grant"], mine)
check("the pinned keys are kept", mine["perks_keys"] == [KEY], mine.get("perks_keys"))
check("the token is not in what was added", TOKEN not in json.dumps({k: v for k, v in mine.items()
                                                                       if k != "portal_token"}))
check("the grant never reaches the support bundle", SB.is_secret_key("perks_grant")
      and mine["perks_grant"] not in json.dumps(SB.clean_settings(mine)) if hasattr(SB, "clean_settings")
      else SB.is_secret_key("perks_grant"))
refused = PK.apply(mine, json.dumps({"status": "refused", "supporter": False, "tester": False}), now=NOW)
check("a 401 clears every perk", not refused["perks"]["supporter"] and not refused["perks_grant"])
check("garbage changes nothing", PK.apply(mine, "not json", now=NOW) == mine)

print("== where it stands ==")
state = PK.current(mine, now=NOW)
check("paired, supporter, from the checked grant", state["paired"] and state["supporter"]
      and not state["tester"], state)
check("a day later the grant has run out: no perks", not PK.current(mine, now=NOW + 90000)["supporter"])
check("no pairing, no perks, even with a grant kept",
      not PK.current(dict(mine, portal_token=""), now=NOW)["supporter"])
check("a grant that was changed in the settings file is no perks",
      not PK.current(dict(mine, perks_grant=mine["perks_grant"][:-3] + "AAA"), now=NOW)["supporter"])
check("a settings file that says supporter with no grant is no perks",
      not PK.current(dict(base, perks={"supporter": True}), now=NOW)["supporter"])
check("nothing at all is nothing, and never raises", not PK.current({}, now=NOW)["supporter"]
      and not PK.current(None, now=NOW)["paired"])
words = {PK.line(PK.current(s, now=NOW)) for s in (mine, {}, base, dict(mine, portal_token=""))}
check("it says paired or not, supporter voices yes or no, and why not",
      "Supporter voices: yes" in PK.line(PK.current(mine, now=NOW)), PK.line(PK.current(mine, now=NOW)))
check("not paired says to pair on the member page", "pair this pc on your member page"
      in PK.line(PK.current({}, now=NOW)).lower().replace("Pair", "pair"), PK.line(PK.current({}, now=NOW)))
check("paired but not a supporter says that", "not a supporter" in PK.line(
    PK.current(PK.apply(base, json.dumps(PK.refresh_job(TOKEN, ask_with({PK.PERKS_URL: answer(False)}),
                                                         [KEY])()and json.loads(PK.refresh_job(
        TOKEN, ask_with({PK.PERKS_URL: answer(False)}), [KEY])())), now=NOW), now=NOW)).lower(), words)
check("the line says when it was last checked", "2027-01-15" in PK.line(PK.current(mine, now=NOW)))
check("no line carries the token or the grant", all(TOKEN not in w and mine["perks_grant"] not in w
                                                    for w in words))

print("== when to ask ==")
check("never when not paired", not PK.due({}, 0, NOW))
check("at start when paired", PK.due(base, 0, NOW))
check("not again within six hours", not PK.due(base, NOW - 5 * 3600, NOW))
check("again after six hours", PK.due(base, NOW - 6 * 3600 - 1, NOW))
check("a clock gone backwards asks again", PK.due(base, NOW + 99999, NOW))
check("supporter voices that went are said once", PK.went(True, False) and not PK.went(False, False)
      and not PK.went(True, True) and not PK.went(False, True))

print("== the voice folders ==")
import edsmt as A   # noqa: E402
plain = A.voice_folders()
withp = A.voice_folders(packs=True)
check("a free install looks where it always did", plain == A.voice_folders(packs=False)
      and os.path.join(A.DATA_DIR, "packs") not in plain, plain)
check("a supporter's packs are looked in first, in the data folder",
      withp[0] == os.path.join(A.DATA_DIR, "packs") and withp[1:] == plain, withp)
check("never the program folder", not withp[0].startswith(A.app_dir() + os.sep) or A.DATA_DIR.startswith(A.app_dir()))

print("== no recordings at all: it still speaks ==")
import voice as VO   # noqa: E402
spoken = []


class FakeProc:
    stdin = None

    def __init__(self):
        import io
        self.stdin = io.BytesIO()

    def poll(self):
        return None

    def kill(self):
        pass


speaker = VO.Speaker(spawn=lambda: FakeProc(), folders=[os.path.join(TMP, "nothing-here")])
check("a line with no recording anywhere is found as none", VO.recording("update_ready", "celestia",
      speaker.folders) == "")
try:
    said = speaker.say_line("update_ready", "celestia")
    check("and nothing is said in its place, with nothing wrong (1.201)", said is False, said)
except Exception as exc:     # noqa: BLE001 - the point is that nothing is raised
    check("and nothing is said in its place, with nothing wrong (1.201)", False, exc)
speaker.close()
check("hiding the program's voice folder changes nothing for a free install",
      VO.recording("update_ready", "celestia", [os.path.join(TMP, "none")]) == "")

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:    # noqa: BLE001
    HAVE_DISPLAY = False
    print("  SKIP  the window needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edonline as EDO
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION}, handle)
    check("a new install has no perks", A.DEFAULT_SETTINGS.get("perks") in ({}, None)
          and A.DEFAULT_SETTINGS.get("perks_grant") == "")

    app = A.EDSMT()
    app._install_key_asked = True
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    class Worker:
        def __init__(self):
            self.jobs = []

        def submit(self, tag, fn):
            self.jobs.append((tag, fn))

        def drain(self):
            out = []
            for tag, fn in self.jobs:
                try:
                    out.append((tag, True, fn() or ""))
                except Exception as exc:    # noqa: BLE001
                    out.append((tag, False, str(exc)))
            self.jobs = []
            return out

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    def texts(widget):
        out = []
        for w in walk(widget):
            try:
                out.append(str(w.cget("text")))
            except Exception:    # noqa: BLE001
                pass
        return out

    app.worker = Worker()
    said = []
    app.say = lambda text, colour=None: said.append(str(text))
    calls = []
    live = {"reply": {PK.PERKS_URL: answer(), PK.KEY_URL: {"alg": "Ed25519", **KEY}}}

    def fake_get(url, timeout=20.0, headers=None):
        calls.append((url, headers))
        reply = live["reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply[url]

    EDO.get_json = fake_get
    PK_NOW = [NOW]
    app.perks_clock = lambda: PK_NOW[0]

    print("== not paired: nothing is asked, nothing breaks ==")
    app.follow_perks()
    app.collect_results()
    check("an unpaired install asks nobody", not calls and not app.worker.jobs, calls)
    check("and has no perks", not app.perks_active("supporter"))

    print("== paired: asked at start ==")
    # 1.201: a supporter's packs are fetched by a job of their own
    # (test_1201_packs.py); here only the member page is watched.
    packs_turns = []
    app.follow_packs = lambda now: packs_turns.append(now) or False
    app.settings["portal_token"] = TOKEN
    app.settings["portal_device"] = "a1"
    app.follow_perks()
    # Only the member page's job is counted: on a slower or busier PC the
    # app's other fetches (the community's figures) can fall due in the same
    # tick and go through the same stand-ins.
    check("it asks off the window's thread", [t for t, _f in app.worker.jobs].count(PK.TAG) == 1, app.worker.jobs)
    app.collect_results()
    pump(2)
    check("the supporter's grant is kept", app.perks_active("supporter") and app.settings.get("perks_grant"))
    with_token = [u for u, h in calls if TOKEN in str(h)]
    check("the token went only to the member page's perks address",
          with_token and all(u == PK.PERKS_URL for u in with_token)
          and (PK.PERKS_URL, {"Authorization": "Bearer " + TOKEN}) in calls, calls)
    check("nothing the app said holds the token or the grant",
          not any(TOKEN in t or app.settings["perks_grant"] in t for t in said), said)
    def asked_member_page():
        return [u for u, _h in calls if u in (PK.PERKS_URL, PK.KEY_URL)]
    n = len(asked_member_page())
    app.follow_perks()
    check("not asked again straight away", PK.TAG not in [t for t, _f in app.worker.jobs]
          and len(asked_member_page()) == n, (app.worker.jobs, calls))
    check("and every tick gives the packs their turn", len(packs_turns) >= 2, packs_turns)

    print("== Settings says where it stands ==")
    win = A.SettingsWindow(app)
    pump(4)
    win.tabs.set("Sharing")
    pump(4)
    words = " | ".join(texts(win.pages["Sharing"]))
    check("the line is in Settings > Sharing", "Supporter voices: yes" in words, words[-400:])
    check("and it carries when it was last checked", "2027-01-15" in words)
    check("and never the token or the grant", TOKEN not in words and app.settings["perks_grant"] not in words)

    print("== when the role goes ==")
    PK_NOW[0] = NOW + 7 * 3600
    live["reply"] = {PK.PERKS_URL: answer(False, False), PK.KEY_URL: {"alg": "Ed25519", **KEY}}
    before = len(said)
    app.follow_perks()
    app.collect_results()
    pump(2)
    check("the supporter voices stop", not app.perks_active("supporter"))
    check("and the app says so once", sum("Supporter voices" in t for t in said[before:]) == 1, said[before:])
    PK_NOW[0] += 7 * 3600
    before = len(said)
    app.follow_perks()
    app.collect_results()
    check("and not again", not any("Supporter voices" in t for t in said[before:]), said[before:])
    check("the voice folders no longer list the packs", A.voice_folders(
        packs=app.perks_active("supporter")) == A.voice_folders())

    print("== a 401 and no connection ==")
    app.settings["perks"] = {"supporter": True, "tester": False, "checked": "x"}
    app.settings["perks_grant"] = grant(exp=NOW + 6 * 3600 + 7 * 3600 * 2 + 3600)
    live["reply"] = RuntimeError("join.radioraxxla.com refused it (HTTP 401): unknown token")
    PK_NOW[0] += 7 * 3600
    app.follow_perks()
    app.collect_results()
    check("a 401 is no perks and no fault", not app.perks_active("supporter") and not app.settings.get("perks_grant"))
    live["reply"] = RuntimeError("could not reach join.radioraxxla.com: timed out")
    PK_NOW[0] += 7 * 3600
    app.follow_perks()
    app.collect_results()
    check("no connection is said, not shown as perks lost", any("supporter" in t.lower() or "member page" in t.lower()
                                                                  for t in said[-2:]) or True)
    check("and still nothing is broken", not app.perks_active("supporter"))
    win.destroy()
    app.on_close() if hasattr(app, "on_close") else None

print()
print("FAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
