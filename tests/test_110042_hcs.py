"""1.10042: the HCS Voice Packs link, always shown with what it is.

A way to support EDSMT that costs a commander nothing extra: the author's
affiliate link to HCS Voice Packs. It is in the welcome window beside the
donation button, at the end of Help, and on the EDSMT page - and wherever
it is, the words saying it is an affiliate link are in sight beside it,
not kept for when the mouse rests on it.

    python tests/test_110042_hcs.py
"""
import io
import os
import re
import sys
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import welcome as WL  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def read(*parts):
    with io.open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


print("== the link ==")
url = getattr(WL, "HCS_URL", "")
bits = urlparse(url)
query = parse_qs(bits.query)
check("it goes to the HCS store, over https", bits.scheme == "https" and bits.netloc == "www.hcsvoicepacks.com", url)
check("with the author's reference", query.get("sca_ref") == ["4748595.5BP6LlL1r0"], query)
check("and says it came from EDSMT, so its part can be seen", query.get("sca_source") == ["EDSMT"], query)
check("no product name made up by hand: the store itself", bits.path in ("", "/"), bits.path)
check("the button says whose packs they are", getattr(WL, "HCS_LABEL", "") == "HCS Voice Packs")
words = getattr(WL, "HCS_WORDS", "")
check("the words beside it say it is an affiliate link", "affiliate link" in words.lower(), words)
check("who earns", "Radio Raxxla earns a commission" in words, words)
check("and that it costs nothing extra", "no extra cost to you" in words, words)

print("== in the app ==")
app = read("edsmt.py")
check("the welcome window has the button", "WL.HCS_LABEL" in app and "WL.HCS_URL" in app)
check("with the words in sight, as a label of their own (the welcome test sees them on the window)",
      "text=WL.HCS_WORDS" in app and "ctk.CTkLabel(partner" in app)
check("Help ends with it, named for what it is",
      '("Voice packs: HCS (affiliate link)", lambda: self.open_page(WL.HCS_URL))' in app)

print("== on the page ==")
page = read("site", "index.html")
box = re.search(r'<p class="note" data-hcs>(.*?)</p>', page, re.S)
check("the page names it, under Install", box is not None)
inner = box.group(1) if box else ""
check("the link is the site's own HCS link, marked as sponsored",
      'data-link="hcsStore"' in inner and 'rel="noopener sponsored"' in inner, inner)
check("with the same words beside it", "affiliate link" in inner.lower() and "no extra cost to you" in inner, inner)

print("== the guide ==")
guide = read("docs", "GUIDE.md")
check("the guide says what the link is", "HCS Voice Packs" in guide and "affiliate link" in guide)

print("== run with the rest ==")
check("this file is in the list", "test_110042_hcs.py" in read("tests", "run_all.py"))

print()
print("FAILURES: %d" % len(fails))
for label in fails:
    print("  - " + label)
sys.exit(1 if fails else 0)
