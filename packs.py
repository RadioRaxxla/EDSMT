"""Supporter voice packs (1.201): fetched, checked and kept for this PC.

A supporter's grant from the member page - or a staff key - lets EDSMT
fetch the extra recordings the API lists for it. Each file is checked
against the SHA-256 the list gives and kept in the data folder as
voice/<pack>/<name>.rrv, sealed with a key kept for this PC: the recordings
are Radio Raxxla's (ASSETS-LICENCE.txt) and play only within EDSMT. voice.py
finds them like any recording and plays them from memory.

The seal: a SHA-256 keystream with a random nonce, and an HMAC-SHA256 tag so
a changed byte is refused. The key is 32 random bytes, protected with
Windows' own data protection for this user on this PC, through an object
tests replace; elsewhere it is kept as it is, readable only by its owner.

A pack comes whole: the map offers it as one file, fetched in one go, and
every recording in it is checked against the list before it is kept - so
the whole voice arrives together. A handful of new recordings, or a pack the
map does not offer whole, is fetched one file at a time, a few with a pause
between; a fetch that is refused stops there, and what is left is carried on
with later, in this run or the next.

Plain functions and two small classes. The calls to the API are handed in.
"""
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import urllib.parse
import zipfile

SEALED = ".rrv"
MAGIC = b"RRV1"
NONCE = 16
TAG_BYTES = 16
KEY_FILE = "pack.key"
MANIFEST = "packs.json"
LIST_PATH = "/v1/packs"
JOB_TAG = "packs"
TIMEOUT_S = 30.0
# The pace of the fetch: this many files in one go, this long before the
# next few; longer after the map said it was busy, and longer again when the
# list could not be had at all.
SLICE = 10
SLICE_GAP_S = 10.0
BUSY_GAP_S = 90.0
RETRY_S = 600.0
# A pack whole (1.201): with more than this many of its files to fetch, the
# pack's one file is asked for. How long that one request may take between
# bytes, and the most EDSMT will take - for the file, and for one recording
# unpacked from it.
ARCHIVE_OVER = 12
ARCHIVE_TIMEOUT_S = 120.0
ARCHIVE_MAX = 400 * 1024 * 1024
MEMBER_MAX = 20 * 1024 * 1024
PACK_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
NAME_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
NAME_DEPTH = 3


# -- the seal -------------------------------------------------------------------

def _keys(key):
    return (hashlib.sha256(b"rrv-enc" + key).digest(),
            hashlib.sha256(b"rrv-mac" + key).digest())


def _stream(enc, nonce, length):
    out = bytearray()
    count = 0
    while len(out) < length:
        out += hashlib.sha256(enc + nonce + count.to_bytes(8, "big")).digest()
        count += 1
    return bytes(out[:length])


def _xor(data, stream):
    if not data:
        return b""
    return (int.from_bytes(data, "little") ^ int.from_bytes(stream, "little")).to_bytes(len(data), "little")


def seal(key, data, nonce=None):
    """`data` sealed with `key`: MAGIC, a nonce, the bytes, a tag."""
    enc, mac = _keys(key)
    nonce = nonce or secrets.token_bytes(NONCE)
    body = _xor(bytes(data), _stream(enc, nonce, len(data)))
    tag = hmac.new(mac, MAGIC + nonce + body, hashlib.sha256).digest()[:TAG_BYTES]
    return MAGIC + nonce + body + tag


def unseal(key, blob):
    """The bytes `seal` sealed, or None for anything else: another key, a
    changed byte, a file that is not one."""
    blob = bytes(blob or b"")
    if len(blob) < len(MAGIC) + NONCE + TAG_BYTES or not blob.startswith(MAGIC):
        return None
    enc, mac = _keys(key)
    nonce = blob[len(MAGIC):len(MAGIC) + NONCE]
    body, tag = blob[len(MAGIC) + NONCE:-TAG_BYTES], blob[-TAG_BYTES:]
    want = hmac.new(mac, MAGIC + nonce + body, hashlib.sha256).digest()[:TAG_BYTES]
    if not hmac.compare_digest(tag, want):
        return None
    return _xor(body, _stream(enc, nonce, len(body)))


# -- the key, kept for this PC ---------------------------------------------------

class PlainProtector:
    """Away from Windows: the key as it is, in a file only its owner reads."""

    def protect(self, data):
        return bytes(data)

    def unprotect(self, data):
        return bytes(data)


class WindowsProtector:
    """Windows' own data protection (CryptProtectData) for this user."""

    def _call(self, name, data):
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        buffer = ctypes.create_string_buffer(bytes(data), len(data))
        given = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        out = Blob()
        crypt = ctypes.windll.crypt32
        call = getattr(crypt, name)
        # CRYPTPROTECT_UI_FORBIDDEN: never a prompt over the game.
        if not call(ctypes.byref(given), None, None, None, None, 0x1, ctypes.byref(out)):
            raise OSError("Windows would not %s the key" % ("protect" if name == "CryptProtectData" else "open"))
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    def protect(self, data):
        return self._call("CryptProtectData", data)

    def unprotect(self, data):
        return self._call("CryptUnprotectData", data)


def protector():
    """The protector for this computer."""
    return WindowsProtector() if os.name == "nt" else PlainProtector()


class Vault:
    """The key for this PC's packs, kept in `folder`, and the files it seals.

    A key that cannot be opened - the folder copied from another PC, or
    another Windows user - is replaced by a new one; `fresh` is then True and
    the packs are fetched again."""

    def __init__(self, folder, protect=None):
        self.folder = folder
        self.protect = protect or protector()
        self.fresh = False
        self._key = None

    def key(self):
        if self._key is not None:
            return self._key
        path = os.path.join(self.folder, KEY_FILE)
        try:
            with open(path, "rb") as handle:
                key = self.protect.unprotect(handle.read())
            if len(key) == 32:
                self._key = key
                return key
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        key = secrets.token_bytes(32)
        os.makedirs(self.folder, exist_ok=True)
        temp = path + ".part"
        with open(temp, "wb") as handle:
            handle.write(self.protect.protect(key))
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        os.replace(temp, path)
        self.fresh = True
        self._key = key
        return key

    def write(self, path, data):
        """`data` sealed at `path` + .rrv (once), written whole or not at all."""
        target = path if path.endswith(SEALED) else path + SEALED
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        temp = target + ".part"
        with open(temp, "wb") as handle:
            handle.write(seal(self.key(), data))
        os.replace(temp, target)
        return target

    def read(self, path):
        """The bytes of a sealed file, or None."""
        try:
            with open(path, "rb") as handle:
                return unseal(self.key(), handle.read())
        except (OSError, ValueError):
            return None


# -- what the API lists, fetched -------------------------------------------------

def store_path(root, pack, name):
    """Where a pack's file is kept - root/voice/<pack>/<name>.rrv - or None
    for a name that is not a plain one."""
    parts = str(name or "").split("/")
    if not (PACK_NAME.match(str(pack or "")) and 1 <= len(parts) <= NAME_DEPTH
            and all(NAME_PART.match(p) and p not in (".", "..") for p in parts)
            and parts[-1].lower().endswith(".wav")):
        return None
    return os.path.join(root, "voice", pack, *parts) + SEALED


def wanted(listing):
    """[(pack, name, sha256, path-part)] from the API's list; anything that
    is not a plain name or a SHA-256 is left out."""
    out = []
    for entry in (listing or {}).get("packs") or []:
        pack = str((entry or {}).get("pack") or "")
        for item in (entry or {}).get("files") or []:
            name, sha = str(item.get("name") or ""), str(item.get("sha256") or "").lower()
            if store_path("", pack, name) is None or not re.fullmatch(r"[0-9a-f]{64}", sha):
                continue
            out.append((pack, name, sha))
    return out


def _read_manifest(root):
    try:
        with open(os.path.join(root, MANIFEST), encoding="utf-8") as handle:
            got = json.load(handle)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_manifest(root, book):
    os.makedirs(root, exist_ok=True)
    temp = os.path.join(root, MANIFEST + ".part")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(book, handle, sort_keys=True)
    os.replace(temp, os.path.join(root, MANIFEST))


def archives(listing):
    """{pack: (bytes, sha256)} for the packs the API's list offers as one
    file; an offer that is not a size and a SHA-256 is no offer."""
    out = {}
    for entry in (listing or {}).get("packs") or []:
        pack, offer = str((entry or {}).get("pack") or ""), (entry or {}).get("archive")
        if not (PACK_NAME.match(pack) and isinstance(offer, dict)):
            continue
        size, sha = offer.get("bytes"), str(offer.get("sha256") or "").lower()
        if isinstance(size, int) and not isinstance(size, bool) and 0 < size <= ARCHIVE_MAX \
                and re.fullmatch(r"[0-9a-f]{64}", sha):
            out[pack] = (size, sha)
    return out


def _sizes(listing):
    """{"pack/name": bytes} as the list gives them."""
    out = {}
    for entry in (listing or {}).get("packs") or []:
        for item in (entry or {}).get("files") or []:
            size = (item or {}).get("bytes")
            if isinstance(size, int) and not isinstance(size, bool):
                out["%s/%s" % ((entry or {}).get("pack"), (item or {}).get("name"))] = size
    return out


def take_whole(blob, offer, lacking, sizes, vault, book):
    """Keep, from a pack's one file, each recording in `lacking` -
    [(ident, name, sha, path)] - that is in it and matches the SHA-256 the
    list gives. How many were kept; ValueError when the file is not the one
    the list described, or not a zip at all.

    Only the names in `lacking` are looked for: nothing else in the file is
    read or written, and a recording whose size is not the listed one, or is
    more than MEMBER_MAX, is passed over without being unpacked."""
    blob = bytes(blob or b"")
    if len(blob) != offer[0] or hashlib.sha256(blob).hexdigest() != offer[1]:
        raise ValueError("not the file the list described")
    got = 0
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as whole:
            for ident, name, sha, path in lacking:
                try:
                    info = whole.getinfo(name)
                except KeyError:
                    continue
                if info.file_size > MEMBER_MAX or (ident in sizes and info.file_size != sizes[ident]):
                    continue
                try:
                    data = whole.read(info)
                except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, NotImplementedError):
                    continue
                if hashlib.sha256(data).hexdigest() != sha:
                    continue
                vault.write(path[:-len(SEALED)], data)
                book[ident] = sha
                got += 1
    except zipfile.BadZipFile:
        raise ValueError("not a zip") from None
    return got


def sync(listing, fetch, root, vault, most=0, skip=(), fetch_archive=None, no_archive=()):
    """Bring the packs in `root` into line with the API's list: fetch what
    is missing or changed, keep it sealed when its SHA-256 matches, take away
    what is no longer listed.

    A pack whole first: with `fetch_archive` (fetch_archive(pack) -> bytes)
    and more than ARCHIVE_OVER of a pack's files to fetch, the pack's one
    file is asked for when the list offers it, and every recording wanted is
    taken from it ("whole" names the packs that came so). A pack whose one
    file could not be had or used is named in "no_archive"; hand those back
    as `no_archive` and it is not asked for again.

    Then file by file (fetch(pack, name) -> bytes) for what is still
    lacking. `most`: at most this many asked for in one call (0: all of
    them); the rest are "left" for the next call, which carries on from
    there. A fetch that raises - the map busy, or out of reach - ends the
    asking at once ("stopped"), with nothing counted as failed. A file that
    arrives wrong is "failed", named in "bad" and passed over; hand those
    names back as `skip` and they are not asked for again.

    A summary back: got, kept, failed, removed, left, stopped, bad, whole,
    no_archive."""
    vault.key()
    book = {} if vault.fresh else _read_manifest(root)
    done = {"got": 0, "kept": 0, "failed": 0, "removed": 0, "left": 0, "stopped": False, "bad": [],
            "whole": [], "no_archive": []}
    keep = set()
    skip = set(skip or ())
    asked = 0
    listed = wanted(listing)
    if not listed:
        # An empty list is the API having nothing to say just now, not an
        # order to throw away what was fetched.
        done["kept"] = len(book)
        return done
    # -- a pack whole, where there is more than a handful to fetch ----------
    offers = archives(listing) if fetch_archive is not None else {}
    lacking = {}
    for pack, name, sha in listed:
        ident = "%s/%s" % (pack, name)
        path = store_path(root, pack, name)
        if pack in offers and ident not in skip and not (book.get(ident) == sha and os.path.isfile(path)):
            lacking.setdefault(pack, []).append((ident, name, sha, path))
    for pack in sorted(lacking):
        if pack in set(no_archive or ()) or len(lacking[pack]) <= ARCHIVE_OVER:
            continue
        try:
            took = take_whole(fetch_archive(pack), offers[pack], lacking[pack], _sizes(listing), vault, book)
        except (OSError, RuntimeError, ValueError, MemoryError):
            # Not to be had, or not what the list described: the files are
            # asked for one by one below, and it is not asked for again.
            done["no_archive"].append(pack)
            continue
        done["got"] += took
        done["whole"].append(pack)
    # What has just come whole is "got", not "kept" from before.
    came = {item[0] for pack in done["whole"] for item in lacking[pack] if book.get(item[0]) == item[2]}
    # -- file by file --------------------------------------------------------
    for pack, name, sha in listed:
        ident = "%s/%s" % (pack, name)
        path = store_path(root, pack, name)
        keep.add(ident)
        if book.get(ident) == sha and os.path.isfile(path):
            if ident not in came:
                done["kept"] += 1
            continue
        if ident in skip:
            done["failed"] += 1
            done["bad"].append(ident)
            continue
        if done["stopped"] or (most and asked >= most):
            done["left"] += 1
            continue
        asked += 1
        try:
            data = fetch(pack, name)
        except (OSError, RuntimeError, ValueError):
            # Busy or out of reach: asking for the next would only be
            # refused too. It is left, with the rest, for later.
            done["stopped"] = True
            done["left"] += 1
            continue
        if not data or hashlib.sha256(data).hexdigest() != sha:
            done["failed"] += 1
            done["bad"].append(ident)
            continue
        vault.write(path[:-len(SEALED)], data)
        book[ident] = sha
        done["got"] += 1
    for ident in sorted(set(book) - keep):
        pack, _sep, name = ident.partition("/")
        path = store_path(root, pack, name)
        try:
            if path and os.path.isfile(path):
                os.remove(path)
        except OSError:
            continue
        book.pop(ident, None)
        done["removed"] += 1
    vault.fresh = False
    _write_manifest(root, book)
    return done


def auth(perks_state, staff_token):
    """The header that asks for the packs: a supporter's grant, else a staff
    key (staff have every voice), else None - nothing is asked."""
    state = perks_state or {}
    if state.get("supporter") and state.get("grant"):
        return {"Authorization": "Bearer " + str(state["grant"])}
    token = str(staff_token or "").strip()
    if token:
        return {"Authorization": "Bearer " + token}
    return None


# About how long one go takes on an ordinary connection, for the estimate.
SLICE_WORK_S = 2.0


def minutes_for(left):
    """About how many minutes `left` files take at this pace: at least 1."""
    try:
        goes = -(-max(0, int(left)) // SLICE)
    except (TypeError, ValueError):
        return 1
    return max(1, int(round(goes * (SLICE_GAP_S + SLICE_WORK_S) / 60.0)))


def sync_job(base_url, header, get_json, get_bytes, root, vault, most=0, state=None):
    """The worker's job: the list; a pack whole where the list offers it
    and there is more than a handful to fetch; then up to `most` of the
    files still lacking (0: all). JSON back - sync()'s summary.

    `state`: a dict the caller keeps for one run of several jobs. The list
    is asked for once and kept in it, with the names of files that arrived
    wrong; when nothing is left the list is dropped, so the next run asks
    for it afresh."""
    state = state if state is not None else {}

    def job():
        listing = state.get("listing")
        if listing is None:
            listing = get_json(base_url + LIST_PATH, timeout=TIMEOUT_S, headers=header)
            state["listing"] = listing

        def fetch(pack, name):
            url = "%s%s/%s/%s" % (base_url, LIST_PATH, pack, urllib.parse.quote(name))
            return get_bytes(url, timeout=TIMEOUT_S, headers=header)

        def fetch_archive(pack):
            return get_bytes("%s%s/%s.zip" % (base_url, LIST_PATH, pack),
                             timeout=ARCHIVE_TIMEOUT_S, headers=header)

        done = sync(listing, fetch, root, vault, most=most, skip=state.get("bad") or (),
                    fetch_archive=fetch_archive, no_archive=state.get("no_archive") or ())
        state["bad"] = sorted(set(state.get("bad") or ()) | set(done["bad"]))
        state["no_archive"] = sorted(set(state.get("no_archive") or ()) | set(done["no_archive"]))
        if not done["left"]:
            state.clear()
        return json.dumps(done)
    return job
