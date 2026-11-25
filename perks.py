"""What a paired install may have: supporter voices and tester builds (1.10042).

A paired EDSMT asks the member page at start and about every six hours what
the commander is allowed. The answer carries a grant the member page has
signed. EDSMT checks the grant on this computer, against the public key it
has pinned by key id (the previous key honoured while the page changes
over), and keeps the answer - never the token - in the settings.

With no pairing, a 401, an expired grant or a grant that does not check,
there are no perks: the Basic lines in the voice picked, and nothing else
changes.

Plain functions. The calls to the member page are handed in, so the checks
never reach it; the Settings line and the timer are thin wiring in edsmt.py.
"""
import base64
import json
import time

import signing

PERKS_URL = "https://join.radioraxxla.com/pair/perks"
KEY_URL = "https://join.radioraxxla.com/pair/perks-key"
TOOL = "edsmt"
# The worker's tag, so the answer is never shown as it came.
TAG = "perks"
EVERY_S = 6 * 3600
TIMEOUT_S = 20.0
_KEYS_MOST = 4
_cache = {}


def _unb64(text):
    text = str(text)
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key_ok(key):
    if not isinstance(key, dict):
        return False
    kid, public = key.get("kid"), key.get("public_key")
    if not (isinstance(kid, str) and 0 < len(kid) <= 40 and isinstance(public, str)):
        return False
    return len(signing.decode(public)) == 32


def _signed_claims(grant, keys):
    """The claims of a grant whose signature checks against the pinned key
    with its key id, for this tool - whatever its expiry. Kept for a moment
    so that asking again every tick costs nothing."""
    pinned = tuple((k["kid"], k["public_key"]) for k in keys or () if _key_ok(k))
    ident = (grant, pinned)
    if ident in _cache:
        return _cache[ident]
    claims = None
    try:
        p64, s64 = str(grant).split(".")
        payload, sig = _unb64(p64), _unb64(s64)
        found = json.loads(payload)
        if isinstance(found, dict) and found.get("tool") == TOOL:
            for kid, public in pinned:
                if kid == found.get("kid") and signing.verify(signing.decode(public), payload, sig):
                    claims = found
                    break
    except (ValueError, TypeError):
        claims = None
    if len(_cache) > 32:
        _cache.clear()
    _cache[ident] = claims
    return claims


def verify_grant(grant, keys, now=None):
    """The grant's claims, or None: it must be for this tool, signed by a
    pinned key with the key id it names, and not yet expired."""
    claims = _signed_claims(grant, keys)
    if claims is None or not isinstance(claims.get("exp"), int) or isinstance(claims.get("exp"), bool):
        return None
    return claims if claims["exp"] > (time.time() if now is None else now) else None


def keys_from_answer(answer):
    """[current, previous] from the member page's key answer; only keys that
    are Ed25519, have an id and are 32 bytes."""
    if not isinstance(answer, dict) or str(answer.get("alg") or "Ed25519") != "Ed25519":
        return []
    out = []
    for key in (answer, answer.get("previous")):
        if _key_ok(key):
            out.append({"kid": key["kid"], "public_key": key["public_key"]})
    return out[:_KEYS_MOST]


def _refused(exc):
    return "HTTP 401" in str(exc)


def refresh_job(token, get, known_keys):
    """The worker's job: ask for the perks with `get` (edonline.get_json) and
    check the grant. JSON back: status ok, refused (a 401) or bad-grant, the
    two roles from the grant's own claims, when the member page checked, the
    grant and the keys now pinned. A failure to reach the page raises."""
    def job():
        try:
            reply = get(PERKS_URL, timeout=TIMEOUT_S, headers={"Authorization": "Bearer " + str(token)})
        except RuntimeError as exc:
            if _refused(exc):
                return json.dumps({"status": "refused", "supporter": False, "tester": False})
            raise
        reply = reply if isinstance(reply, dict) else {}
        grant = reply.get("grant")
        keys = [k for k in known_keys or () if _key_ok(k)]
        claims = verify_grant(grant, keys) if keys else None
        if claims is None:
            # No key yet, or a new key id: fetch the member page's key.
            fresh = keys_from_answer(get(KEY_URL, timeout=TIMEOUT_S))
            if fresh:
                keys = fresh
                claims = verify_grant(grant, keys)
        if claims is None:
            return json.dumps({"status": "bad-grant", "supporter": False, "tester": False,
                               "keys": keys})
        return json.dumps({"status": "ok", "supporter": claims.get("supporter") is True,
                           "tester": claims.get("tester") is True,
                           "checked": str(reply.get("checked") or "")[:40],
                           "grant": grant, "keys": keys})
    return job


def apply(settings, text, now=None):
    """The settings with the member page's answer kept. Anything that is not
    an answer changes nothing. The token is never touched."""
    try:
        got = json.loads(text)
    except (ValueError, TypeError):
        return settings
    if not isinstance(got, dict):
        return settings
    out = dict(settings or {})
    keys = [k for k in got.get("keys") or [] if _key_ok(k)]
    if keys:
        out["perks_keys"] = keys
    if got.get("status") == "ok":
        out["perks"] = {"supporter": bool(got.get("supporter")), "tester": bool(got.get("tester")),
                        "checked": str(got.get("checked") or "")}
        out["perks_grant"] = str(got.get("grant") or "")
    else:
        out["perks"] = {"supporter": False, "tester": False,
                        "checked": str((out.get("perks") or {}).get("checked") or "")}
        out["perks_grant"] = ""
    return out


def current(settings, now=None):
    """Where the perks stand now: paired, supporter, tester, the grant to
    send with a request (only while it holds), when last checked and why
    not. Checked again from the signed grant every time, so an edited
    settings file or a grant that has run out gives nothing."""
    settings = settings if isinstance(settings, dict) else {}
    kept = settings.get("perks") if isinstance(settings.get("perks"), dict) else {}
    out = {"paired": bool(str(settings.get("portal_token") or "").strip()), "supporter": False,
           "tester": False, "grant": "", "checked": str(kept.get("checked") or ""), "why": ""}
    if not out["paired"]:
        out["why"] = "not paired"
        return out
    grant = settings.get("perks_grant")
    if not grant:
        out["why"] = "no answer from the member page yet"
        return out
    claims = verify_grant(grant, settings.get("perks_keys"), now)
    if claims is None:
        out["why"] = "the member page's last answer has run out or does not check"
        return out
    out["supporter"] = claims.get("supporter") is True
    out["tester"] = claims.get("tester") is True
    out["grant"] = str(grant)
    if not out["supporter"]:
        out["why"] = "not a supporter"
    return out


def stamp(checked):
    """2027-01-15T08:00:00Z as 2027-01-15 08:00 UTC."""
    text = str(checked or "").strip()
    if len(text) >= 16 and text[10] == "T":
        return text[:10] + " " + text[11:16] + " UTC"
    return text


def line(state):
    """The Settings line, in plain words."""
    state = state or {}
    if not state.get("paired"):
        return "Not paired. Supporter voices: no - pair this PC on your member page."
    if state.get("supporter"):
        said = "Paired. Supporter voices: yes."
    elif state.get("why") == "not a supporter":
        said = "Paired. Supporter voices: no - you are not a supporter on the member page."
    else:
        said = "Paired. Supporter voices: no - %s." % (state.get("why") or "not checked yet")
    if state.get("tester"):
        said += " Tester builds: yes."
    when = stamp(state.get("checked"))
    return said + (" Last checked %s." % when if when else " Not checked yet.")


def due(settings, asked_at, now):
    """Whether to ask the member page: paired, and not within six hours of
    the last time (a clock that went backwards asks again)."""
    if not (isinstance(settings, dict) and str(settings.get("portal_token") or "").strip()):
        return False
    try:
        gap = float(now) - float(asked_at)
    except (TypeError, ValueError):
        return True
    return gap >= EVERY_S or gap < 0


def went(was, now):
    """Whether a perk has just gone."""
    return bool(was) and not now
