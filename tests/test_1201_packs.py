"""1.201: supporter voice packs - fetched, kept sealed, played from memory.

Supporters, and Radio Raxxla staff, get the rest of Celestia's recordings.
They are Radio Raxxla's (ASSETS-LICENCE.txt) and play only within EDSMT.

  * packs.py: the packs a supporter grant (or a staff token) may have are
    fetched from the API, each file checked against the SHA-256 it lists,
    and kept sealed with a key kept for this PC - never as a plain WAV;
  * voice.py finds a sealed recording like a plain one and plays it from
    memory; the comm sound and a distance's join of sealed recordings are
    kept sealed too;
  * the free install holds one take of every Basic line, and nothing else.

    python tests/test_1201_packs.py
"""
import base64
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-packs1201-")

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def wav_bytes(seconds=0.2, rate=22050, tone=0):
    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for n in range(int(seconds * rate)):
            value = int(8000 * (((n + tone) // 20) % 2 * 2 - 1))
            frames += value.to_bytes(2, "little", signed=True)
        handle.writeframes(bytes(frames))
    return out.getvalue()


try:
    import packs as PK2
except ImportError as exc:
    PK2 = None
    check("packs.py is there", False, exc)

import voice as VO          # noqa: E402
import audiodev as AD       # noqa: E402

if PK2 is not None:
    print("== sealed: nobody can play the file outside EDSMT ==")
    key = b"k" * 32
    plain = wav_bytes()
    blob = PK2.seal(key, plain)
    check("the sealed file is not a wave", not blob.startswith(b"RIFF") and b"WAVE" not in blob[:64])
    check("and opens again with the key", PK2.unseal(key, blob) == plain)
    check("not with another key", PK2.unseal(b"x" * 32, blob) is None)
    tampered = bytearray(blob)
    tampered[40] ^= 1
    check("a changed byte is refused", PK2.unseal(key, bytes(tampered)) is None)
    check("two seals of one file differ", PK2.seal(key, plain) != blob)

    print("== the key is this PC's ==")

    class Marked:
        """Stands in for Windows' own protection: what it protects, only it opens."""
        def __init__(self, mark):
            self.mark = mark

        def protect(self, data):
            return self.mark + bytes(b ^ 0x5A for b in data)

        def unprotect(self, data):
            if not data.startswith(self.mark):
                raise OSError("not ours")
            return bytes(b ^ 0x5A for b in data[len(self.mark):])

    folder = os.path.join(TMP, "vault")
    vault = PK2.Vault(folder, Marked(b"PC1:"))
    first = vault.key()
    check("a key is made once and kept", len(first) == 32 and PK2.Vault(folder, Marked(b"PC1:")).key() == first)
    kept = open(os.path.join(folder, PK2.KEY_FILE), "rb").read()
    check("never kept as it is", first not in kept)
    other = PK2.Vault(folder, Marked(b"PC2:"))
    check("copied to another PC it cannot be opened, and a new key is made",
          other.key() != first and other.fresh)
    path = os.path.join(TMP, "sealed", "line.wav")
    written = vault.write(path, plain)
    check("written sealed, beside its name with .rrv", written == path + PK2.SEALED and os.path.isfile(written)
          and not os.path.exists(path))
    check("read back whole", vault.read(written) == plain)
    check("the other PC's vault cannot read it", other.read(written) is None)

    print("== fetched from the API, checked, kept sealed ==")
    files = {"celestia": {"online_2.wav": wav_bytes(tone=3), "chatty/react_jump-2.wav": wav_bytes(tone=5),
                          "dist_km_2.wav": wav_bytes(tone=7)}}
    listing = {"packs": [{"pack": pack, "files": [{"name": name, "bytes": len(data),
                                                   "sha256": hashlib.sha256(data).hexdigest()}
                                                  for name, data in sorted(found.items())]}
                         for pack, found in files.items()]}
    listing["packs"][0]["files"].append({"name": "../../evil.wav", "bytes": 4, "sha256": "0" * 64})
    listing["packs"].append({"pack": "../up", "files": [{"name": "x.wav", "bytes": 1, "sha256": "0" * 64}]})
    asked = []

    def fetch(pack, name):
        asked.append((pack, name))
        return files[pack][name]

    root = os.path.join(TMP, "packs")
    vault = PK2.Vault(root, Marked(b"PC1:"))
    done = PK2.sync(listing, fetch, root, vault)
    check("every good file fetched", sorted(asked) == sorted(("celestia", n) for n in files["celestia"]), asked)
    check("names that try to leave the folder are not", not any(".." in p or ".." in n for p, n in asked))
    check("three got", done.get("got") == 3, done)
    everything = [os.path.join(d, f) for d, _s, fs in os.walk(root) for f in fs]
    check("no plain wave anywhere in the packs folder",
          not any(f.endswith(".wav") for f in everything)
          and not any(open(f, "rb").read(4) == b"RIFF" for f in everything), everything)
    check("where the voice looks: voice/<pack>/<name>.rrv",
          os.path.isfile(os.path.join(root, "voice", "celestia", "chatty", "react_jump-2.wav.rrv")))
    asked.clear()
    done = PK2.sync(listing, fetch, root, vault)
    check("asked again, nothing is fetched twice", asked == [] and done.get("kept") == 3, (asked, done))
    bad = json.loads(json.dumps(listing))
    bad["packs"][0]["files"][0]["sha256"] = "1" * 64
    files_before = set(everything)
    asked.clear()
    done = PK2.sync(bad, fetch, root, vault)
    check("a file that does not match its SHA-256 is not kept", done.get("failed") == 1, done)
    short = {"packs": [{"pack": "celestia", "files": [f for f in listing["packs"][0]["files"]
                                                      if f["name"] == "online_2.wav"]}]}
    done = PK2.sync(short, fetch, root, vault)
    check("a file the API no longer lists is taken away", done.get("removed") == 2
          and not os.path.exists(os.path.join(root, "voice", "celestia", "dist_km_2.wav.rrv")), done)
    done = PK2.sync({"packs": []}, fetch, root, vault)
    check("an empty list from the API takes nothing away", done.get("removed") == 0
          and os.path.isfile(os.path.join(root, "voice", "celestia", "online_2.wav.rrv")), done)
    done = PK2.sync(listing, fetch, root, PK2.Vault(root, Marked(b"PC2:")))
    check("a new key (another PC) fetches everything again", done.get("got") == 3, done)

    print("== who asks for them ==")
    check("a supporter's grant", PK2.auth({"supporter": True, "grant": "g.s"}, "") == {"Authorization": "Bearer g.s"})
    check("a staff key, with no grant", PK2.auth({"supporter": False, "grant": ""}, "staff-1")
          == {"Authorization": "Bearer staff-1"})
    check("a supporter grant first, when there are both",
          PK2.auth({"supporter": True, "grant": "g.s"}, "staff-1") == {"Authorization": "Bearer g.s"})
    check("neither: nothing is asked", PK2.auth({"supporter": False, "grant": ""}, "") is None)

    print("== the voice finds and plays a sealed recording ==")
    vault = PK2.Vault(root, Marked(b"PC1:"))
    PK2.sync(listing, fetch, root, vault)
    plain_dir = os.path.join(TMP, "free")
    os.makedirs(os.path.join(plain_dir, "voice", "celestia"))
    with open(os.path.join(plain_dir, "voice", "celestia", "online.wav"), "wb") as fh:
        fh.write(wav_bytes(tone=1))
    folders = [root, plain_dir]
    takes = VO.recording_takes("online", "celestia", folders)
    check("the plain take and the sealed one are both takes of the line",
          len(takes) == 2 and takes[1].endswith("online_2.wav.rrv"), takes)
    check("a sealed later take is found", VO.recording("react_jump", "celestia", folders, detail="chatty",
                                                         take=2).endswith("react_jump-2.wav.rrv"))

    class Stand:
        def __init__(self):
            self.lines = []
            self.stdin = self

        def write(self, raw):
            self.lines.extend(x for x in raw.decode("utf-8").split("\n") if x)

        def flush(self):
            pass

        def poll(self):
            return None

        def kill(self):
            pass

    import time as _time
    stand = Stand()
    sp = VO.Speaker(spawn=lambda: stand, folders=folders, cache_dir=os.path.join(TMP, "cache"))
    sp.vault = vault
    sp.comms = False
    sp._random.seed(4)
    sent = []
    for _ in range(6):
        sp.say_line("online", "celestia")
    deadline = _time.time() + 10
    while _time.time() < deadline and len([x for x in stand.lines if x[:2] in ("W ", "B ")]) < 6:
        _time.sleep(0.05)
    plays = [x for x in stand.lines if x[:2] in ("W ", "B ")]
    check("a sealed take goes to the player as its sound, not as a file name",
          any(x.startswith("B ") for x in plays) and not any(x.endswith(".rrv") for x in plays), plays)
    sealed_plays = [x for x in plays if x.startswith("B ")]
    if sealed_plays:
        check("and it is the recording itself",
              base64.b64decode(sealed_plays[0][2:]) == files["celestia"]["online_2.wav"])
    stand.lines.clear()
    sp.comms = True
    sp.say_line("react_jump", "celestia", detail="chatty") if False else None
    sp._last_take = {}
    found = VO.recording("online", "celestia", [root], take=1)
    found = VO.recording_takes("online", "celestia", [root])[0]
    sp._sent(("FX", found, "srv"), "words")
    deadline = _time.time() + 20
    while _time.time() < deadline and not stand.lines:
        _time.sleep(0.05)
    check("its comm sound is worked out and played the same way",
          stand.lines and stand.lines[-1].startswith("B "), stand.lines[-1:][:1])
    cached = [os.path.join(d, f) for d, _s, fs in os.walk(os.path.join(TMP, "cache")) for f in fs]
    check("and kept sealed in the cache: no plain wave of it there",
          cached and not any(f.endswith(".wav") for f in cached), cached)
    stand.lines.clear()
    parts = [VO.recording_takes("online", "celestia", [root])[0],
             VO.recording_takes("dist_km_2", "celestia", [root])[0]]
    line = sp._join(("JOIN", parts, "srv", False, "words"))
    check("a distance joined from sealed recordings is kept sealed", isinstance(line, str)
          and line.startswith("W ") and line.endswith(PK2.SEALED), line)
    sp.close()

print("== the app: a supporter or a staff key, and nobody else ==")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
try:
    import edsmt as A
except Exception as exc:          # no Tk here: the module checks above still count
    A = None
    print("  SKIP  the app's wiring needs Tk (%s)" % exc)
if A is not None:
    A.DATA_DIR = os.path.join(TMP, "appdata-data")
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = {"community_token": ""}
    supporter = {"on": False}
    app.perks_active = lambda role: supporter["on"] and role == "supporter"

    class Spk:
        folders, vault = [], None

    spk = Spk()
    check("a free install: no packs", app.packs_allowed() is False and app.voice_packs(spk) is False
          and spk.vault is None and not any(f.endswith("packs") for f in spk.folders), spk.folders)
    supporter["on"] = True
    check("a supporter: the packs folder first, and the vault",
          app.voice_packs(spk) is True and spk.folders[0].endswith("packs") and spk.vault is not None, spk.folders)
    supporter["on"] = False
    app.settings["community_token"] = "staff-key"
    check("a staff key, no supporter grant: every voice", app.packs_allowed() is True)
    app.settings["community_token"] = ""
    src = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
    check("her hints, reactions and asides need the packs",
          "or not self.packs_allowed():" in src.split("def follow_cues", 1)[1][:2500])
    check("the fetch answer is taken", "if tag == PX.JOB_TAG:" in src and "self.follow_packs(" in src)

print("== the players take a sound as well as a file ==")
check("Windows' player plays it from memory, nothing written",
      "'B'" in VO.SPEECH_SCRIPT and "FromBase64String" in VO.SPEECH_SCRIPT and "MemoryStream" in VO.SPEECH_SCRIPT)
check("the device player writes it for the moment it plays and takes it away",
      "'B'" in AD.DEVICE_SPEECH_SCRIPT and "FromBase64String" in AD.DEVICE_SPEECH_SCRIPT
      and AD.DEVICE_SPEECH_SCRIPT.count("Remove-Item") >= 2)
check("a sound that will not play is said plainly", VO.explain_problem("E B bad").startswith("A recording could not"))
check("a later take's words come from take 1 when take 1 is what plays",
      VO.take_words(os.path.join("voice", "celestia", "online_2.wav.rrv"), "celestia")
      == VO.take_words(os.path.join("voice", "celestia", "online_2.wav"), "celestia"))

print("== the free install: one take of every Basic line ==")
for theme in ("celestia", "ship_computer", "flight_controller", "on_air"):
    base = os.path.join(REPO, "voice", theme)
    names = sorted(os.path.relpath(os.path.join(d, f), base).replace(os.sep, "/")
                   for d, _s, fs in os.walk(base) for f in fs if f.endswith(".wav"))
    check("%s: exactly the %d Basic lines" % (theme, len(VO.LINES)),
          names == sorted("%s.wav" % line for line in VO.LINES), (len(names), names[:5]))
iss = open(os.path.join(REPO, "build", "installer.iss"), encoding="utf-8").read()
check("an update clears the old program files first, so the moved recordings go",
      'Type: filesandordirs; Name: "{app}\\_internal"' in iss)

print("== nothing public says they are locked ==")
for name in ("README.md", os.path.join("docs", "GUIDE.md"), "CHANGELOG.md"):
    text = open(os.path.join(REPO, name), encoding="utf-8").read().lower()
    if name == "CHANGELOG.md":
        text = text.split("## 1.2\n")[0]
    about = [p for p in text.split("\n\n") if "voice" in p or "pack" in p or "recording" in p]
    said = [p[:80] for p in about if re.search(r"\b(locked|encrypt\w*|sealed|drm)\b", p)]
    check("%s does not say the voices are locked, encrypted or sealed" % name, not said, said)

print("\nFAILURES: %d" % len(fails))
sys.exit(1 if fails else 0)
