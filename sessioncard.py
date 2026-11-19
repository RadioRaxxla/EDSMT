"""The session card (1.10040, #151): one Rhino session as a picture, for a
stream or a Discord channel.

Built in two steps, like the map picture it borrows from (mapimage.py):

  card_facts    what the card says about a session - whose, where, when,
                tonnes by commodity, credits, credits an hour, merits and
                time mined - from the session's row and what the app has
                worked out about it. No imaging library.
  render_card   paints those facts with Pillow: the map picture of the
                session as a thumbnail when there is one, and the EDSMT badge
                small in a corner. It answers the texts it wrote as well as
                the picture, so what a card says is checked without reading
                pixels.

Pillow is optional, as for map pictures: mapimage.pillow_status() says why a
card cannot be made, and the button says it.

Since 1.10042 the card is drawn in the weekly card's style (the community
map's own, which he picked for every card): the dark cockpit glass with its
grid and amber bar, four tiles of big figures, three bracketed panels, and
the Rajdhani and Share Tech Mono type, which ship with EDSMT in fonts/ under
the SIL Open Font License.
"""
import calendar
import os
import re
import sys
import time

import mapimage as MI
import survey as SV

SIZE = (1280, 720)                      # 16:9, the weekly card's size
LEFT, RIGHT = 56, 1224
GAP = 24
TILES = (190, 372)                      # the row of four tiles, top and bottom
PANELS = (396, 640)                     # the row of three panels
MAP_BOX = (530, 408, 750, 628)          # the map thumbnail, square, in the middle panel
BADGE_PX = 56
TONNES_SHOWN = 5
SITE = MI.SITE

# The weekly card's colours.
INK = (5, 9, 20)
PANEL = (11, 19, 34)
EDGE = (38, 54, 80)
GRID = (10, 17, 31)
AMBER = (240, 160, 48)
GOLD = (255, 200, 96)
TEXT = (228, 234, 244)
MUTED = (146, 158, 178)
FAINT = (80, 94, 118)
_FACES = {"bold": "Rajdhani-Bold.ttf", "semi": "Rajdhani-SemiBold.ttf",
          "medium": "Rajdhani-Medium.ttf", "mono": "ShareTechMono-Regular.ttf"}
_STYLE = {}
STYLE_FONTS_FOUND = None                # set at the first font asked for


def _font_folders():
    here = os.path.dirname(os.path.abspath(__file__))
    out = [os.path.join(here, "fonts")]
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        out.insert(0, os.path.join(bundle, "fonts"))
    return out


def style_font(kind, size):
    """The weekly card's type at a size: Rajdhani (bold, semi, medium) or
    Share Tech Mono (mono). Without the files, the map picture's own type,
    so a card is never lost for want of a font."""
    global STYLE_FONTS_FOUND
    key = (kind, int(size))
    if key in _STYLE:
        return _STYLE[key]
    from PIL import ImageFont
    found = None
    for folder in _font_folders():
        try:
            found = ImageFont.truetype(os.path.join(folder, _FACES.get(kind, _FACES["medium"])), int(size))
            break
        except (OSError, ValueError):
            continue
    if STYLE_FONTS_FOUND is None:
        STYLE_FONTS_FOUND = found is not None
    if found is None:
        found = MI._font(int(size), kind in ("bold", "semi"))
    _STYLE[key] = found
    return found

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec")


def _whole(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return 0 if number != number else int(round(number))


def _hours_text(hours):
    minutes = max(0, int(round(float(hours or 0) * 60)))
    if minutes < 60:
        return "%dm" % minutes
    return "%dh %02dm" % divmod(minutes, 60)


def _span(first, last):
    """"02:48 to 05:18 UTC", with the dates when it ran past midnight."""
    if not first or not last or last < first:
        return ""
    a, b = time.gmtime(first), time.gmtime(last)
    if (a.tm_year, a.tm_yday) == (b.tm_year, b.tm_yday):
        return "%02d:%02d to %02d:%02d UTC" % (a.tm_hour, a.tm_min, b.tm_hour, b.tm_min)
    return "%d %s %02d:%02d to %d %s %02d:%02d UTC" % (
        a.tm_mday, _MONTHS[a.tm_mon - 1], a.tm_hour, a.tm_min,
        b.tm_mday, _MONTHS[b.tm_mon - 1], b.tm_hour, b.tm_min)


def card_facts(row, cmdr="", estimate=None, merits=None, merits_estimated=False, hide=None):
    """What the card says about one session. `row` is the session as the
    books keep it; `estimate` what the app worked out it is worth (its
    "value" counts what is still unsold at the best price known); `merits`
    the merits it earned; `hide` streamer mode's rule for a line of text,
    which the system and body pass through. Never raises."""
    row = dict(row or {})
    hide = hide or (lambda text: text)
    mined = SV.unpack_counts(row.get("mined"))
    tonnes = sorted(((SV.canonical(name) or name, int(count)) for name, count in mined.items()
                     if int(count) > 0), key=lambda pair: (-pair[1], pair[0]))
    hours = SV.session_hours(row)
    sold = float(SV.earned(row) or 0)
    value = float((estimate or {}).get("value") or 0)
    # Once anything is sold the card says what it sold for: the estimate
    # counted unsold tonnes at the best price known, and a sale at another
    # station is a little under it - not a reason to call the sale an
    # estimate (1.10042).
    estimated = sold <= 0 and value > 0
    credits = value if estimated else sold
    first = SV._epoch(row.get("started"))
    last = SV._epoch(row.get("ended") or row.get("closed"))
    moment = time.gmtime(first) if first else None
    earned = _whole(merits) if merits is not None else 0
    return {
        "cmdr": str(cmdr or row.get("cmdr") or "").strip(),
        "system": str(hide(str(row.get("system") or "").strip()) or ""),
        "body": str(hide(str(row.get("body") or "").strip()) or ""),
        "started": first,
        "date": ("%d %s %d" % (moment.tm_mday, _MONTHS[moment.tm_mon - 1], moment.tm_year))
        if moment else "",
        "span": _span(first, last),
        "tonnes": tonnes,
        "tonnes_total": sum(count for _name, count in tonnes),
        "credits": _whole(credits),
        "credits_estimated": bool(estimated),
        "cr_hr": _whole(credits / hours) if hours > 0 else 0,
        "merits": earned or None,
        "merits_estimated": bool(merits_estimated) if earned else False,
        "hours": hours,
        "time_mined": _hours_text(hours),
    }


def card_name(row):
    """card_<system>_<body>_<yyyymmdd-hhmm>.png from the session's row, safe
    on Windows, and named like a map picture so the same tidying keeps them
    in check. The real names, whatever the card shows."""
    row = row or {}
    first = SV._epoch(row.get("started"))
    moment = time.gmtime(first or time.time())
    return "card_%s_%s_%s.png" % (MI._clean(row.get("system")), MI._clean(row.get("body")),
                                  time.strftime("%Y%m%d-%H%M", moment))


def find_map(folder, system, body, first, last=0):
    """The map picture of `body` saved while a session ran - the last one,
    by the time in its name - or "". `last` of 0 is a session still running.
    A session card is never mistaken for a map. Never raises."""
    if not first:
        return ""
    pattern = re.compile(r"^%s_%s_[A-Za-z0-9_]{1,8}_(\d{8}-\d{4})\.png$"
                         % (re.escape(MI._clean(system)), re.escape(MI._clean(body))))
    low, high = float(first) - 60, float(last or time.time()) + 120
    best = None
    try:
        names = os.listdir(folder)
    except OSError:
        return ""
    for name in names:
        found = pattern.match(name)
        if not found or name.startswith("card_"):
            continue
        try:
            at = calendar.timegm(time.strptime(found.group(1), "%Y%m%d-%H%M"))
        except ValueError:
            continue
        if low <= at <= high and (best is None or at > best[0]):
            best = (at, os.path.join(folder, name))
    return best[1] if best else ""


def map_plot(image):
    """The map itself out of a map picture: the square plot, without the
    title over it or the legend beside it - the names are in the title, and
    the card says those itself. A picture of another shape is used whole."""
    width, height = image.size
    full_w, full_h = MI.SIZE
    if not width or abs(height / float(width) - full_h / float(full_w)) > 0.01:
        return image
    scale = width / float(full_w)
    side = full_h - 150
    box = (24, 96, 24 + side, 96 + side)
    return image.crop(tuple(int(round(v * scale)) for v in box))


def load_badge(path):
    """The EDSMT badge as a Pillow picture, or None when it is missing or
    will not load - a card without its badge is still a card."""
    try:
        from PIL import Image
        with Image.open(path) as source:
            source.load()
            return source.convert("RGBA")
    except Exception:
        return None


def _cmdr(name):
    name = str(name or "").strip()
    if not name:
        return ""
    return name if name.lower().startswith("cmdr ") else "CMDR " + name


def _short(number):
    """A big figure to fit a tile: 234.3M, 1.23B, 42,396."""
    value = float(number or 0)
    if abs(value) >= 1e9:
        return "%.2fB" % (value / 1e9)
    if abs(value) >= 1e6:
        return "%.1fM" % (value / 1e6)
    return "{:,}".format(int(round(value)))


def _tiles(facts):
    """The four tiles: (big figure, label)."""
    out = [("%d t" % facts["tonnes_total"], "Mined"),
           (_short(facts["credits"]), "Credits, est." if facts["credits_estimated"] else "Credits"),
           (_short(facts["cr_hr"]), "Cr/hr, est." if facts["credits_estimated"] else "Cr/hr")]
    if facts.get("merits"):
        out.append(("{:,}".format(facts["merits"]), "Merits, est." if facts["merits_estimated"] else "Merits"))
    else:
        out.append((facts["time_mined"], "Time mined"))
    return out


def panel_boxes(has_map=True):
    """The boxes the card draws its brackets round: four tiles, three panels."""
    boxes = []
    width = (RIGHT - LEFT - 3 * GAP) / 4.0
    for i in range(4):
        x = LEFT + i * (width + GAP)
        boxes.append((int(x), TILES[0], int(x + width), TILES[1]))
    width = (RIGHT - LEFT - 2 * GAP) / 3.0
    for i in range(3):
        x = LEFT + i * (width + GAP)
        boxes.append((int(x), PANELS[0], int(x + width), PANELS[1]))
    return boxes


def _glass():
    """The dark cockpit glass every weekly picture is drawn on."""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", SIZE, INK)
    draw = ImageDraw.Draw(img)
    for x in range(0, SIZE[0], 48):
        draw.line((x, 0, x, SIZE[1]), fill=GRID)
    for y in range(0, SIZE[1], 48):
        draw.line((0, y, SIZE[0], y), fill=GRID)
    glow = Image.new("L", SIZE, 0)
    ImageDraw.Draw(glow).ellipse((760, -360, 1600, 300), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.composite(Image.new("RGB", SIZE, (70, 44, 12)), img, glow)
    ImageDraw.Draw(img).rectangle((0, 0, SIZE[0], 4), fill=AMBER)
    return img


def _brackets(draw, box, colour=AMBER, length=16, width=3):
    x0, y0, x1, y1 = box
    for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        draw.line((x, y, x + dx * length, y), fill=colour, width=width)
        draw.line((x, y, x, y + dy * length), fill=colour, width=width)


def render_card(facts, map_image=None, colour=None, badge=None, version=""):
    """The card as a Pillow RGB image, and the texts on it, in the weekly
    card's style. `map_image` is a map picture to show as a thumbnail;
    `colour` gives a commodity's colour; `badge` the EDSMT badge; `version`
    the version as shown. Raises ImportError without Pillow."""
    from PIL import Image, ImageDraw

    img = _glass()
    draw = ImageDraw.Draw(img)
    written = []

    def text(xy, value, kind, size, fill, room=None, anchor="la", least=None):
        """Write a line; with `room`, smaller type first, then cut short."""
        value = " ".join(str(value).split())
        font = style_font(kind, size)
        if room:
            least = least or max(12, int(size * 0.6))
            while font.getlength(value) > room and size > least:
                size -= 2
                font = style_font(kind, size)
            if font.getlength(value) > room:
                while len(value) > 2 and font.getlength(value + "\u2026") > room:
                    value = value[:-1]
                value = value.rstrip() + "\u2026"
        written.append(value)
        try:
            draw.text(xy, value, font=font, fill=fill, anchor=anchor)
        except ValueError:
            draw.text(xy, value, font=font, fill=fill)
        return font.getlength(value)

    def tint(name):
        if colour is not None:
            try:
                return colour(name)
            except Exception:
                pass
        return MI.DEFAULT_COLOUR

    # The frame: what and when, whose, the day; a rule; where.
    head = "EDSMT RHINO SESSION" + ((" \u00b7 " + facts["span"].upper()) if facts.get("span") else "")
    text((LEFT, 34), head, "semi", 24, MUTED, room=RIGHT - LEFT)
    text((LEFT, 64), _cmdr(facts.get("cmdr")) or "Rhino session", "bold", 58, TEXT, room=760, least=34)
    if facts.get("date"):
        text((RIGHT, 124), facts["date"], "semi", 28, MUTED, anchor="rs")
    draw.line((LEFT, 140, LEFT + 140, 140), fill=AMBER, width=4)
    draw.line((LEFT + 150, 140, RIGHT, 140), fill=EDGE, width=1)
    x = LEFT
    if facts.get("body"):
        x += text((LEFT, 150), facts["body"], "semi", 22, AMBER, room=700) + 14
    if facts.get("system"):
        text((x, 150), facts["system"], "medium", 22, MUTED, room=max(60, RIGHT - x))

    boxes = panel_boxes(map_image is not None)
    for box in boxes:
        draw.rounded_rectangle(box, radius=6, fill=PANEL, outline=EDGE, width=1)
        _brackets(draw, box)

    # Four tiles of big figures.
    for (x0, y0, x1, _y1), (big, label) in zip(boxes[:4], _tiles(facts)):
        text((x0 + 22, y0 + 14), big, "mono", 88, GOLD, room=x1 - x0 - 44, least=40)
        text((x0 + 22, y0 + 122), label, "semi", 30, MUTED, room=x1 - x0 - 44)

    # What was mined.
    x0, y0, x1, _y1 = boxes[4]
    text((x0 + 22, y0 + 16), "MINED", "semi", 22, AMBER)
    y = y0 + 52
    for name, count in facts["tonnes"][:TONNES_SHOWN]:
        r = 7
        draw.ellipse((x0 + 30 - r, y + 13 - r, x0 + 30 + r, y + 13 + r), fill=tint(name))
        text((x1 - 22, y), "%d t" % count, "mono", 26, TEXT, anchor="ra")
        text((x0 + 46, y), name, "medium", 26, TEXT, room=x1 - x0 - 46 - 22 - 90)
        y += 34
    hidden = len(facts["tonnes"]) - TONNES_SHOWN
    if hidden > 0:
        text((x0 + 46, y), "+ %d more" % hidden, "medium", 20, FAINT)

    # The map, as it stood, kept to its own shape inside its box.
    mx0, my0, mx1, my1 = MAP_BOX
    if map_image is not None:
        draw.rectangle((mx0 - 1, my0 - 1, mx1 + 1, my1 + 1), fill=INK, outline=EDGE)
        picture = map_plot(map_image.convert("RGB"))
        room_w, room_h = mx1 - mx0, my1 - my0
        scale = min(room_w / float(picture.size[0]), room_h / float(picture.size[1]))
        fitted = picture.resize((max(1, int(picture.size[0] * scale)),
                                 max(1, int(picture.size[1] * scale))), Image.LANCZOS)
        img.paste(fitted, (mx0 + (room_w - fitted.size[0]) // 2, my0 + (room_h - fitted.size[1]) // 2))
    else:
        text(((mx0 + mx1) / 2.0, (my0 + my1) / 2.0), "No map picture", "medium", 22, FAINT, anchor="mm")

    # The session in words.
    x0, y0, x1, _y1 = boxes[6]
    text((x0 + 22, y0 + 16), "TIME MINED", "semi", 22, AMBER)
    text((x0 + 22, y0 + 48), facts["time_mined"], "bold", 44, TEXT, room=x1 - x0 - 44)
    credits = "{:,} Cr".format(facts["credits"])
    lines = [facts.get("span") or "",
             ("%.1f t/hr" % (facts["tonnes_total"] / facts["hours"])) if facts.get("hours") else "",
             ("est. " + credits) if facts["credits_estimated"] else credits,
             "Not sold yet" if facts["credits_estimated"] else "Sold"]
    y = y0 + 112
    for line in [l for l in lines if l][:4]:
        text((x0 + 22, y), line, "medium", 24, MUTED, room=x1 - x0 - 44)
        y += 32

    # The foot: where to find it, the version, the badge.
    text((LEFT, 702), SITE, "semi", 26, AMBER, anchor="ls")
    text((SIZE[0] - 24 - BADGE_PX - 16, 702), ("EDSMT %s" % version) if version else "EDSMT",
         "medium", 22, FAINT, anchor="rs")
    if badge is not None:
        mark = badge.convert("RGBA").resize((BADGE_PX, BADGE_PX), Image.LANCZOS)
        img.paste(mark, (SIZE[0] - 24 - BADGE_PX, SIZE[1] - 16 - BADGE_PX), mark)
    return img, written
