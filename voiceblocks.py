"""Distances and directions from building blocks (1.10042, G4, #341).

A voice that comes recorded says a distance and a direction by putting
recordings - the blocks - one after another: the line that leads, the
distance, the compass point. Each distance is one recording of the whole
phrase, said as a person says it (dist_m_340 is "three hundred and forty
metres", dist_km_2p4 "two point four kilometres"), so a number is never
put together from its words. "Nearest deposit, 2.4 kilometres north-east"
is the line nearest, then dist_km_2p4, then north_east.

This module is the plain part: which block says what, the words it stands
for (what the Windows voice says in its place) and the joining of the
recordings into one, a short breath between them and no clipped join.
Finding the files and playing them is the Speaker's (voice.py). Nothing
here needs a window.
"""

import array
import hashlib
import math
import os
import sys
import wave

def _distances():
    """Every distance that has its own recording, nearest first: (block id,
    words). Whole metres under ten, tens of metres under a kilometre, tenths
    of a kilometre under ten kilometres, whole kilometres up to ninety-nine."""
    out = [("dist_m_%d" % n, "%d metre%s" % (n, "" if n == 1 else "s")) for n in range(1, 10)]
    out += [("dist_m_%d" % n, "%d metres" % n) for n in range(10, 1000, 10)]
    for km in range(1, 10):
        out.append(("dist_km_%d" % km, "%d kilometre%s" % (km, "" if km == 1 else "s")))
        out += [("dist_km_%dp%d" % (km, tenth), "%d.%d kilometres" % (km, tenth)) for tenth in range(1, 10)]
    out += [("dist_km_%d" % km, "%d kilometres" % km) for km in range(10, 100)]
    return tuple(out)


DISTANCES = _distances()
# The sixteen compass points, clockwise from north: (block id, words).
COMPASS = (("north", "north"), ("north_north_east", "north-north-east"),
           ("north_east", "north-east"), ("east_north_east", "east-north-east"),
           ("east", "east"), ("east_south_east", "east-south-east"),
           ("south_east", "south-east"), ("south_south_east", "south-south-east"),
           ("south", "south"), ("south_south_west", "south-south-west"),
           ("south_west", "south-west"), ("west_south_west", "west-south-west"),
           ("west", "west"), ("west_north_west", "west-north-west"),
           ("north_west", "north-west"), ("north_north_west", "north-north-west"))

WORDS = dict(DISTANCES)
WORDS.update(dict(COMPASS))
# Every block, in the order of a recording sheet.
ALL_BLOCKS = tuple(ident for ident, _w in DISTANCES) + tuple(ident for ident, _w in COMPASS)

# Joins: silence this quiet at the ends of a recording is not part of it, and
# the first and last few milliseconds are faded so a join cannot click.
GATE = 300
FADE_MS = 5
# The breath between the lead, the distance and the direction.
JOIN_GAP_MS = 130


def block_words(ids):
    """The words the blocks stand for, as the Windows voice would say them."""
    return " ".join(WORDS.get(i, "") for i in ids or ()).strip()


def distance_blocks(metres):
    """The block that says a distance, as a one-block list, said as
    voice.distance_words says it - whole metres under ten, to the nearest
    ten under a kilometre, tenths of a kilometre under ten kilometres, whole
    kilometres beyond - or None for one with no recording: a hundred
    kilometres and more."""
    try:
        value = float(metres)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    value = max(0.0, value)
    if value < 10:
        return ["dist_m_%d" % max(1, int(round(value)))]
    tens = int(round(value / 10.0)) * 10
    if tens < 1000:
        return ["dist_m_%d" % tens]
    km = round(value / 1000.0, 1)
    if km < 10:
        whole, tenth = divmod(int(round(km * 10)), 10)
        return ["dist_km_%dp%d" % (whole, tenth) if tenth else "dist_km_%d" % whole]
    whole = int(round(value / 1000.0))
    return ["dist_km_%d" % whole] if whole < 100 else None


def compass_blocks(bearing):
    """The compass point of a bearing in degrees (0 north, 90 east), as a
    one-block list, or None."""
    try:
        degrees = float(bearing)
    except (TypeError, ValueError):
        return None
    if math.isnan(degrees) or math.isinf(degrees):
        return None
    return [COMPASS[int(math.floor((degrees % 360.0) / 22.5 + 0.5)) % 16][0]]


def direction_blocks(lead, metres, bearing):
    """A whole line: the lead (a line of the pack, "" for none), the
    distance, the compass point. None when any part cannot be said."""
    distance, point = distance_blocks(metres), compass_blocks(bearing)
    if distance is None or point is None:
        return None
    return ([str(lead)] if lead else []) + distance + point


def _read(path):
    """(params, samples) of a 16-bit wave, or None if it is anything else."""
    try:
        with wave.open(path, "rb") as handle:
            params = (handle.getnchannels(), handle.getsampwidth(), handle.getframerate())
            raw = handle.readframes(handle.getnframes())
    except (OSError, EOFError, wave.Error):
        return None
    if params[1] != 2 or params[0] < 1:
        return None
    samples = array.array("h")
    samples.frombytes(raw[:len(raw) - len(raw) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return params, samples


def _trim(samples, channels):
    """The recording without the silence at its ends, faded at both."""
    frames = len(samples) // channels
    start, end = 0, frames
    while start < end and all(abs(samples[start * channels + c]) <= GATE for c in range(channels)):
        start += 1
    while end > start and all(abs(samples[(end - 1) * channels + c]) <= GATE for c in range(channels)):
        end -= 1
    if end <= start:
        return None
    return array.array("h", samples[start * channels:end * channels])


def join_wavs(paths, out_path, gap_ms=0):
    """The recordings one after another as one wave, at out_path: the same
    format throughout, the silence at each end trimmed, `gap_ms` of
    silence between one and the next,
    a few milliseconds of fade so no join is clipped. False - nothing
    written - when one cannot be read, is not 16-bit, differs from the rest
    or is only silence."""
    parts, params = [], None
    for path in paths:
        got = _read(path)
        if got is None:
            return False
        if params is None:
            params = got[0]
        elif got[0] != params:
            return False
        body = _trim(got[1], params[0])
        if body is None:
            return False
        parts.append(body)
    if not parts:
        return False
    channels, _width, rate = params
    fade = max(1, int(rate * FADE_MS / 1000.0))
    out = array.array("h")
    pause = array.array("h", [0] * (max(0, int(rate * float(gap_ms) / 1000.0)) * channels))
    for index, body in enumerate(parts):
        frames = len(body) // channels
        n = min(fade, frames // 2)
        for i in range(n):
            gain = i / float(n)
            for c in range(channels):
                body[i * channels + c] = int(body[i * channels + c] * gain)
                j = (frames - 1 - i) * channels + c
                body[j] = int(body[j] * gain)
        if index:
            out.extend(pause)
        out.extend(body)
    if sys.byteorder == "big":
        out.byteswap()
    temp = out_path + ".part"
    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with wave.open(temp, "wb") as handle:
            handle.setnchannels(channels)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(out.tobytes())
        os.replace(temp, out_path)
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False
    return True


def joined_path(paths, folder, gap_ms=0):
    """Where the join of these recordings is kept: named by what went in,
    their names, sizes and times and the breath between them, so a changed
    recording is joined again."""
    key = hashlib.sha1()
    for path in paths:
        try:
            info = os.stat(path)
            key.update(("%s|%d|%d;" % (path, info.st_size, int(info.st_mtime))).encode("utf-8", "replace"))
        except OSError:
            key.update(("%s|?;" % path).encode("utf-8", "replace"))
    key.update(("gap|%d" % int(gap_ms)).encode("ascii"))
    return os.path.join(folder, "blocks-%s.wav" % key.hexdigest()[:20])
