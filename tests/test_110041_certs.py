"""1.10041: a certificate that has run out in the Windows store no longer
breaks HTTPS.

Windows keeps certificates after they run out. Python hands the whole store
to the TLS library, and the library then takes an out-of-date copy of an
issuer from the store in place of the good copy a site sends - so a site
whose own certificate is fine is refused with "certificate has expired".
That stopped Inara updates on PCs that still held such a copy.

EDSMT now builds its trust from the store's certificates that are still in
date, and every HTTPS request it makes uses that.

The three certificates below were made for this test. No key for them was
kept, so they can sign nothing.

    python tests/test_110041_certs.py
"""
import base64
import calendar
import os
import ssl
import sys
import socket
import tempfile
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-certs-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import certstore as CS    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


# A root in date until 2099; an issuer signed by it that ran out in 2020; and
# the same issuer (same name, same key) signed again and in date until 2099.
ROOT = base64.b64decode(
    "MIIBeDCCAR+gAwIBAgICA+kwCgYIKoZIzj0EAwIwMjEZMBcGA1UECgwQRURTTVQgdGVzdC"
    "BzdWl0ZTEVMBMGA1UEAwwMTWFkZS11cCByb290MCAXDTE5MDEwMTAwMDAwMFoYDzIwOTkx"
    "MjMxMDAwMDAwWjAyMRkwFwYDVQQKDBBFRFNNVCB0ZXN0IHN1aXRlMRUwEwYDVQQDDAxNYW"
    "RlLXVwIHJvb3QwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAATVhEUDP7g80A8CyIf0COSQ"
    "nBN6akzHKC/t9eLY4SjXSZ512LyRHC7vpEejogQeBswDrfwZHSeArg4To2kXLsedoyMwIT"
    "APBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAKBggqhkjOPQQDAgNHADBEAiAO"
    "gjvAjMVLvbGFRMuXOySlu0O9vNid2TksypcxnG0yoQIgDBbMinWqGyChLptvb1rg9/pqqk"
    "nm2yzo0y1NR2GhvuU=")
ISSUER_RUN_OUT = base64.b64decode(
    "MIIBeTCCAR+gAwIBAgICA+owCgYIKoZIzj0EAwIwMjEZMBcGA1UECgwQRURTTVQgdGVzdC"
    "BzdWl0ZTEVMBMGA1UEAwwMTWFkZS11cCByb290MB4XDTE5MDEwMTAwMDAwMFoXDTIwMDEw"
    "MTAwMDAwMFowNDEZMBcGA1UECgwQRURTTVQgdGVzdCBzdWl0ZTEXMBUGA1UEAwwOTWFkZS"
    "11cCBpc3N1ZXIwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAAR93e5YhxS0sfQTqR0Fddxk"
    "SCbz3PbyQq8QyMGbOIpD5W9eZAgp9/BLQCbc5np1U6AgdU5aFHO9I20m+Ne0KZG6oyMwIT"
    "APBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAKBggqhkjOPQQDAgNIADBFAiAS"
    "q2IHlHYLM28BTt6Pps48bRY/3nIJfvq7wFvnqCUskQIhAKHZ9aoVIZr1uEMX/R4425BTeu"
    "YDuG8K58T52t2i2hwA")
ISSUER_IN_DATE = base64.b64decode(
    "MIIBezCCASGgAwIBAgICA+swCgYIKoZIzj0EAwIwMjEZMBcGA1UECgwQRURTTVQgdGVzdC"
    "BzdWl0ZTEVMBMGA1UEAwwMTWFkZS11cCByb290MCAXDTI0MDEwMTAwMDAwMFoYDzIwOTkx"
    "MjMxMDAwMDAwWjA0MRkwFwYDVQQKDBBFRFNNVCB0ZXN0IHN1aXRlMRcwFQYDVQQDDA5NYW"
    "RlLXVwIGlzc3VlcjBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABH3d7liHFLSx9BOpHQV1"
    "3GRIJvPc9vJCrxDIwZs4ikPlb15kCCn38EtAJtzmenVToCB1TloUc70jbSb417QpkbqjIz"
    "AhMA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgGGMAoGCCqGSM49BAMCA0gAMEUC"
    "IHWczdIWZM3AWoumCZDsZ79fk3SWcab85gg4Cr8f92LtAiEAqsVdbiI8AUhLUpLSf5/nJP"
    "j2yEZqVtJSk4sXVMuL8bA=")
SERIAL = {"root": "03E9", "run out": "03EA", "in date": "03EB"}
NOV_2026 = calendar.timegm((2026, 11, 11, 0, 0, 0))
WEB = "1.3.6.1.5.5.7.3.1"       # "may vouch for a web site"
MAIL = "1.3.6.1.5.5.7.3.4"      # "may vouch for e-mail"


def serials(context):
    return sorted(str(info.get("serialNumber")) for info in context.get_ca_certs())


class Store:
    """Stands in for the Windows certificate stores."""

    def __init__(self, **stores):
        self.stores, self.asked = stores, []

    def __call__(self, name):
        self.asked.append(name)
        found = self.stores.get(name, [])
        if isinstance(found, Exception):
            raise found
        return found


print("== which certificates are still in date ==")
kept = CS.in_date([ROOT, ISSUER_RUN_OUT, ISSUER_IN_DATE], NOV_2026)
check("the one that ran out is left out", ISSUER_RUN_OUT not in kept, len(kept))
check("the ones in date are kept, in their order", kept == [ROOT, ISSUER_IN_DATE], len(kept))
check("in 2019 none of the three had run out",
      CS.in_date([ROOT, ISSUER_RUN_OUT], calendar.timegm((2019, 6, 1, 0, 0, 0))) == [ROOT, ISSUER_RUN_OUT])
check("in 2101 all have", CS.in_date([ROOT, ISSUER_IN_DATE], calendar.timegm((2101, 1, 1, 0, 0, 0))) == [])
check("something that is not a certificate is left out, not an error",
      CS.in_date([b"not a certificate", ROOT], NOV_2026) == [ROOT])
check("nor does one in the middle hide what comes after it",
      CS.in_date([ROOT, b"not a certificate", ISSUER_IN_DATE], NOV_2026) == [ROOT, ISSUER_IN_DATE])
check("the same certificate twice is kept once", CS.in_date([ROOT, ROOT], NOV_2026) == [ROOT])
check("nothing in, nothing out", CS.in_date([], NOV_2026) == [])

print("== reading the Windows stores ==")
store = Store(CA=[(ISSUER_RUN_OUT, "x509_asn", True), (ISSUER_IN_DATE, "x509_asn", {WEB, MAIL}),
                  (b"a revocation list", "pkcs_7_asn", True)],
              ROOT=[(ROOT, "x509_asn", True), (ISSUER_IN_DATE, "x509_asn", {MAIL})])
got = CS.store_certificates(store)
check("both stores are read", sorted(store.asked) == ["CA", "ROOT"], store.asked)
check("certificates only, and only those trusted for web sites",
      got == [ISSUER_RUN_OUT, ISSUER_IN_DATE, ROOT], len(got))
check("a store Windows will not open is passed over",
      CS.store_certificates(Store(CA=PermissionError("no"), ROOT=[(ROOT, "x509_asn", True)])) == [ROOT])
check("with no Windows store to read (Linux) there is nothing to filter",
      CS.store_certificates(None) == [] or hasattr(ssl, "enum_certificates"))

print("== the trust EDSMT makes from them ==")
made = CS.context(read=store, now=NOV_2026)
check("the root and the in-date issuer are trusted",
      SERIAL["root"] in serials(made) and SERIAL["in date"] in serials(made), serials(made))
check("the copy that ran out is not there to be picked", SERIAL["run out"] not in serials(made), serials(made))
check("certificates are still required", made.verify_mode == ssl.CERT_REQUIRED)
check("and the name on them still checked", made.check_hostname is True)
check("old protocol versions stay off", made.minimum_version >= ssl.TLSVersion.TLSv1_2, made.minimum_version)
python_own = ssl.create_default_context().verify_flags
check("no check this Python's own default makes is dropped",
      (made.verify_flags & python_own) == python_own, (int(made.verify_flags), int(python_own)))

plain = CS.context(read=Store(), now=NOV_2026)
check("nothing in the stores: the system's own trust, still checking",
      plain.verify_mode == ssl.CERT_REQUIRED and plain.check_hostname is True)


def broken(name):
    raise RuntimeError("the store cannot be read")


safe = CS.context(read=broken, now=NOV_2026)
check("a store that cannot be read at all: the system's own trust, no error",
      isinstance(safe, ssl.SSLContext) and safe.verify_mode == ssl.CERT_REQUIRED)

print("== every request EDSMT makes uses it ==")


def names(made):
    return sorted(type(h).__name__ for h in made.handlers)


def as_urllibs_own(ours):
    """The handlers urllib's own opener has on this machine as it is set up
    now, with the HTTPS one swapped for EDSMT's and nothing else changed."""
    own = [n for n in names(urllib.request.build_opener()) if n != "HTTPSHandler"]
    return names(ours) == sorted(own + ["Handler"])


# urllib leaves its proxy handler out when the machine has no proxy set, so
# which handlers there are depends on the machine. Both cases, made here.
urllibs_getproxies = urllib.request.getproxies
try:
    urllib.request.getproxies = lambda: {"http": "http://127.0.0.1:9", "https": "http://127.0.0.1:9"}
    behind = CS.install(read=Store(), now=NOV_2026)
    check("a proxy set on the machine is still used",
          "ProxyHandler" in names(behind) and as_urllibs_own(behind), names(behind))
    urllib.request.getproxies = lambda: {}
    direct = CS.install(read=Store(), now=NOV_2026)
    check("with none set there is none, as with urllib's own",
          "ProxyHandler" not in names(direct) and as_urllibs_own(direct), names(direct))
finally:
    urllib.request.getproxies = urllibs_getproxies

lazy = Store(CA=[(ISSUER_RUN_OUT, "x509_asn", True), (ISSUER_IN_DATE, "x509_asn", True)],
             ROOT=[(ROOT, "x509_asn", True)])
opener = CS.install(read=lazy, now=NOV_2026)
held = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPSHandler)]
check("the opener has one HTTPS handler, and it is EDSMT's", len(held) == 1 and isinstance(held[0], CS.Handler), held)
check("installing reads nothing: starting the app is not slowed", lazy.asked == [], lazy.asked)
check("redirects and errors are handled as urllib's own does, and nothing else is changed",
      {"HTTPRedirectHandler", "HTTPErrorProcessor"} <= set(names(opener)) and as_urllibs_own(opener),
      names(opener))

# A request to a listener that hangs up at once: it fails, as it should, but
# only after the handler has asked for the trust - which is what is checked.
listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(1)
port = listener.getsockname()[1]


def hang_up():
    try:
        conn, _ = listener.accept()
        conn.close()
    except OSError:
        pass


threading.Thread(target=hang_up, daemon=True).start()
try:
    urllib.request.urlopen("https://127.0.0.1:%d/" % port, timeout=5)
    refused = False
except (urllib.error.URLError, OSError):
    refused = True
listener.close()
check("a server that is not one is still refused", refused)
check("the first HTTPS request is what reads the stores", sorted(lazy.asked) == ["CA", "ROOT"], lazy.asked)
check("with the run-out copy left out", SERIAL["run out"] not in serials(CS.installed())
      and SERIAL["in date"] in serials(CS.installed()), serials(CS.installed()))
first = CS.installed()
check("made once and kept", CS.installed() is first and sorted(lazy.asked) == ["CA", "ROOT"], lazy.asked)

import edonline as EDO    # noqa: E402  (loading it is what installs the trust in the app)
in_use = getattr(urllib.request, "_opener", None)
check("the app's online module installs it when it loads",
      EDO is not None and in_use is not None and any(isinstance(h, CS.Handler) for h in in_use.handlers), in_use)
check("and the trust it will make is a real one, still checking",
      CS.installed().verify_mode == ssl.CERT_REQUIRED and CS.installed().check_hostname is True)
src = open(os.path.join(REPO, "edonline.py"), encoding="utf-8").read()
check("edonline installs the trust itself", "CS.install()" in src or "certstore.install()" in src)

import eddnsend as ES     # noqa: E402
names = [dict(pair[0] for pair in info.get("subject", ())).get("commonName") for info in ES.context().get_ca_certs()]
check("the data network's sender builds on the same trust and keeps its extra root",
      "ISRG Root X2" in names, names[:5])
src = open(os.path.join(REPO, "eddnsend.py"), encoding="utf-8").read()
check("and no longer takes the store as it comes", "create_default_context" not in src)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)
