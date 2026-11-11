"""The certificates EDSMT trusts for HTTPS: the system's, minus the ones that
have run out.

Windows keeps a certificate in its store after it runs out, and Python hands
the whole store to the TLS library as trusted. When a site's issuer is in
the store only as an out-of-date copy, the library takes that copy in place
of the good one the site sends, and the site is refused with "certificate
has expired" although nothing of the site's has. Leaving the run-out
certificates out puts it right and loses nothing: a certificate that has run
out can vouch for nobody.

On Linux the system's own trust is used as it is.

Nothing here is specific to one site, and nothing is ever written.
"""
import http.client
import ssl
import sys
import threading
import time
import urllib.request

# The purpose a store certificate must be trusted for: vouching for a web site.
SERVER_AUTH = "1.3.6.1.5.5.7.3.1"
STORES = ("CA", "ROOT")

_state = {"context": None, "read": None, "now": None}
_lock = threading.Lock()


def store_certificates(read=None) -> list:
    """The certificates the Windows stores trust for web sites, as DER bytes.

    `read` stands in for ssl.enum_certificates, which only Windows has; with
    neither there is nothing to read and the answer is [].
    """
    read = read or getattr(ssl, "enum_certificates", None)
    if read is None:
        return []
    found = []
    for name in STORES:
        try:
            entries = list(read(name))
        except OSError:
            continue        # a store Windows will not open: the other may
        for certificate, encoding, trust in entries:
            if encoding != "x509_asn":
                continue
            if trust is True or SERVER_AUTH in trust:
                found.append(bytes(certificate))
    return found


def _load(into, certificates) -> list:
    """Load DER certificates into the context `into`. Returns the ones it
    took, each once, in the order given."""
    wanted = list(dict.fromkeys(bytes(der) for der in certificates))
    try:
        # All at once, which is far the quickest. The count is checked
        # because a loader stops quietly at the first thing it cannot read.
        into.load_verify_locations(cadata=b"".join(wanted))
        if into.cert_store_stats().get("x509", 0) >= len(wanted):
            return wanted
    except (ssl.SSLError, ValueError, TypeError):
        pass
    taken = []
    for der in wanted:
        try:
            into.load_verify_locations(cadata=der)
        except (ssl.SSLError, ValueError, TypeError):
            continue
        taken.append(der)
    return taken


def in_date(certificates, now=None) -> list:
    """Those of `certificates` (DER bytes) that have not run out by `now`
    (seconds since 1970, the present by default), each once, in the order
    given. Anything that is not a certificate is left out."""
    now = time.time() if now is None else float(now)
    scratch = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    readable = _load(scratch, certificates)
    run_out = set()
    for der, facts in zip(scratch.get_ca_certs(binary_form=True), scratch.get_ca_certs()):
        try:
            ends = ssl.cert_time_to_seconds(facts["notAfter"])
        except (KeyError, ValueError, TypeError):
            continue
        if ends < now:
            run_out.add(bytes(der))
    return [der for der in readable if der not in run_out]


def context(read=None, now=None) -> ssl.SSLContext:
    """What every HTTPS request EDSMT makes is checked against.

    The Windows stores' certificates that are still in date, with the same
    checks Python's own default makes: a certificate is required and the
    name on it must match. Where there is no Windows store, or nothing can
    be read from it, the system's own default - never less than Python
    itself would have done.
    """
    try:
        kept = in_date(store_certificates(read), now)
    except Exception:       # noqa: BLE001 - whatever the store did, fall back
        kept = []
    if not kept:
        return ssl.create_default_context()
    made = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    made.minimum_version = ssl.TLSVersion.TLSv1_2
    if sys.version_info >= (3, 13):
        # The two checks Python's own default gained in 3.13.
        made.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
    _load(made, kept)
    try:
        # A certificate file named by SSL_CERT_FILE or SSL_CERT_DIR, as
        # Python's default honours it (a company proxy's own root, say).
        made.set_default_verify_paths()
    except (ssl.SSLError, OSError):
        pass
    if not made.get_ca_certs():
        return ssl.create_default_context()
    return made


class Handler(urllib.request.HTTPSHandler):
    """HTTPS checked against installed(). The trust is made when the first
    request needs it - on the thread that sends it, never while the window
    is being drawn - and kept."""

    def __init__(self):
        # The parent wants a context of its own; this one is never used.
        super().__init__(context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))

    def https_open(self, req):
        return self.do_open(http.client.HTTPSConnection, req, context=installed())


def install(read=None, now=None):
    """Make every urllib request this process sends use the trust above.
    Costs nothing now: the stores are read when the first request goes.
    Returns the opener it installed."""
    with _lock:
        _state["context"], _state["read"], _state["now"] = None, read, now
    opener = urllib.request.build_opener(Handler())
    urllib.request.install_opener(opener)
    return opener


def installed() -> ssl.SSLContext:
    """The one trust every request shares: made on first use, then kept."""
    with _lock:
        if _state["context"] is None:
            _state["context"] = context(_state["read"], _state["now"])
        return _state["context"]
