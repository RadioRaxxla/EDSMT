"""What every mark on the map is, and which of them are drawn (1.10042).

A tester's two pictures of the map came back with "what are all these small
circles?", "what is this arrow?" and "how can it be removed?". This is the
answer, once, in plain words: the map's key (the "?" on the map, the map's
right-click menu, Help, and the welcome's "How to customise the map"), and a
switch for each layer that can clutter it - on the right-click menu and in
Settings > Overlay > Map and scope. Every switch starts where the map has
always been, except the lines between deposits, which are new and start off.

Plain data and small functions; no window. The map and the scope both read
`layers()` from the settings, so the two never disagree about what is on.
"""

# Each layer: (setting, short name, label on the menu and in Settings,
# drawn as it ships).
LAYERS = (
    ("map_show_border", "border", "Survey border and its centre", True),
    ("map_show_drive", "drive", "Circles to drive", True),
    ("map_show_rings", "rings", "Range rings", True),
    ("map_show_waypoints", "waypoints", "Guided-survey points (waypoints)", True),
    ("map_show_gaps", "gaps", "Unswept gaps (GAP)", True),
    ("map_show_pointer", "pointer", "Pointer to the waypoint, ship or Rhino", True),
    ("map_show_links", "links", "Lines between deposits, zoomed in", False),
)
SETTINGS = {key: default for key, _name, _label, default in LAYERS}
NAMES = tuple(name for _key, name, _label, _default in LAYERS)
_BY_NAME = {name: (key, label, default) for key, name, label, default in LAYERS}

# The words each layer's switch carries as its note in Settings.
TIPS = {
    "map_show_border": "The amber ring where you set the border, and the cross at "
                       "the survey centre, on the map and the scope.",
    "map_show_drive": "The dashed cyan circles: the rings to drive so the scanner "
                      "covers the whole survey area.",
    "map_show_rings": "The faint dotted rings round you, each labelled with its "
                      "distance.",
    "map_show_waypoints": "The guided survey's small circles - where to press your "
                          "mineral scanner if you don't hold it down all the time. "
                          "Off hides them; the guided survey still runs.",
    "map_show_gaps": "Red GAP marks on ground inside the border the scanner has not "
                     "swept yet, with their size.",
    "map_show_pointer": "The line with a dot beside you that points at the next "
                        "waypoint, the ship or the parked Rhino.",
    "map_show_links": "Zoomed in on the map, or at 2x and 4x on the scope: a thin "
                      "line from each deposit to the one nearest it, with its "
                      "length.",
}

# Your own marker: how big it is drawn, as a factor of the standard size.
# "Larger" is what a new install gets: your own place is the one that
# matters most on the map.
MARKER_SIZES = (("Standard", "standard", 1.0), ("Larger", "larger", 1.25),
                ("Largest", "largest", 1.6))
MARKER_SIZE_DEFAULT = "larger"
# White unless another colour is picked (Settings > Theme).
MARKER_WHITE = "#ffffff"

# The key: (what the mark is called, what it is, the layer that hides it or
# "" when it is always drawn). In the order they are usually seen.
KEY = (
    ("Your marker", "The white arrow in the middle is you, pointing the way you "
     "face. Its colour is in Settings > Theme, its size in Settings > Overlay > "
     "Map and scope.", ""),
    ("Waypoint pointer", "The line with a dot beside you points at the next "
     "waypoint (or the ship, or the parked Rhino). It is not you.", "pointer"),
    ("Guided-survey points", "The small circles are the guided survey's "
     "waypoints: where to press your mineral scanner if you don't hold it down "
     "all the time. The ringed one, WP n, is next; grey ones are done. "
     "Right-click one to remove it or skip it.", "waypoints"),
    ("LANDED", "Waypoint 1 is where you landed - where you touched down; your "
     "ship may have left since. Right-click it to remove it.", "waypoints"),
    ("Survey border", "The solid amber ring is the border you set with the "
     "border key; the amber cross is the survey centre, where you logged the "
     "signal.", "border"),
    ("Circles to drive", "The dashed cyan circles are the rings to drive so the "
     "scanner covers the whole area.", "drive"),
    ("Range rings", "The faint dotted rings round you, each with its distance.",
     "rings"),
    ("Swept ground", "The shaded ground is what the scanner has covered as you "
     "drove (driven past, not proven scanned).", ""),
    ("GAP", "A red GAP is a patch inside the border not swept yet, with its "
     "size in km2.", "gaps"),
    ("Deposits", "Round dots are yours, diamonds are other commanders'; a grey "
     "ring is mined out. Bigger dot, more rigs.", ""),
    ("Lines between deposits", "Zoomed in, a thin line joins each deposit to the "
     "nearest one, with its length.", "links"),
    ("Rigs", "A numbered square is a rig, in its commodity's colour; red once it "
     "is too far away. Right-click one to pick it up or change its commodity.",
     ""),
    ("Rig spacing rings", "The red and green bands round each rig are the spacing "
     "rings: red while you are too close for the next rig, green once clear.", ""),
    ("Planning circle", "The dashed green 4.5 km circle is the planning circle "
     "you put down with a right-click; rigs inside it are never too far apart. "
     "It is not a rig.", ""),
    ("Wingmates", "A diamond with a name is a wingmate's Rhino; their rigs and "
     "finds are in their colour. A rig they have collected stays, dashed and "
     "marked collected: in the game it stays until you leave the planet.", ""),
)

# Where the switches are, said once on the key and on the welcome's page.
WHERE_SWITCHES = ("Right-click the map for the switches and the key. The same "
                  "switches, your marker's size and the marker filters are in "
                  "Settings > Overlay > Map and scope; your marker's colour is "
                  "in Settings > Theme.")
TITLE = "How to customise the map"


def layers(settings):
    """{short name: drawn} for every layer, from settings. Anything missing
    is as it ships."""
    settings = settings if isinstance(settings, dict) else {}
    return {name: bool(settings.get(key, default))
            for key, name, _label, default in LAYERS}


def shown(prefs, name):
    """Is this layer drawn, given the map preferences the map or the scope
    was handed (their "layers" entry)? As it ships when not said."""
    found = (prefs or {}).get("layers") if isinstance(prefs, dict) else None
    default = _BY_NAME.get(name, ("", "", True))[2]
    if not isinstance(found, dict) or name not in found:
        return default
    return bool(found[name])


def setting_of(name):
    """The setting that holds a layer's switch, or "" for no such layer."""
    return _BY_NAME.get(name, ("", "", True))[0]


def label_of(name):
    return _BY_NAME.get(name, ("", "", True))[1]


def marker_scale(value):
    """How much bigger than standard your own marker is drawn."""
    text = str(value or "").strip().lower()
    for label, key, scale in MARKER_SIZES:
        if text in (key, label.lower()):
            return scale
    return dict((key, scale) for _l, key, scale in MARKER_SIZES)[MARKER_SIZE_DEFAULT]


def marker_size(value, standard):
    """Your marker's size in pixels, from the setting and the standard size
    of the place it is drawn (12 on the map, 11 on the scope)."""
    return round(float(standard) * marker_scale(value), 1)


def key_lines(prefs=None):
    """The key as (name, words, state) - state "on", "off" or "" for a mark
    that has no switch - in the order shown."""
    out = []
    for name, words, layer in KEY:
        state = ("on" if shown(prefs, layer) else "off") if layer else ""
        out.append((name, words, state))
    return out

