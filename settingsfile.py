"""Settings to and from a file (1.10042).

Save writes the settings as plain JSON with every key and token left out
(the same ones the support bundle removes). Load reads such a file back:
anything the app does not know is ignored, a value of the wrong kind is
ignored, and a key or token in the file is never taken. What is accepted is
laid over the settings in use and goes through the app's own settings load,
which brings an older file up to date. Pure functions, no window.
"""
import json

import supportbundle as SB

MARK = "edsmt_settings_file"
VERSION = 1


def export_text(settings):
    """The settings as the file's text, with no secret in it."""
    kept = {key: value for key, value in dict(settings or {}).items()
            if not SB.is_secret_key(key)}
    return json.dumps({MARK: VERSION, "settings": kept}, indent=2,
                      ensure_ascii=False, default=str)


def _same_kind(value, default):
    if default is None:
        return True
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def read_text(text, defaults):
    """(accepted, ignored, problem). `accepted` is {key: value} for the keys
    the app knows with a value of the right kind; `ignored` lists the keys
    left out; `problem` is "" or a sentence when the file is not one of ours."""
    try:
        data = json.loads(text.lstrip("﻿"))
    except (ValueError, AttributeError):
        return {}, [], "that is not a settings file"
    if not isinstance(data, dict):
        return {}, [], "that is not a settings file"
    body = data.get("settings") if MARK in data else data
    if not isinstance(body, dict):
        return {}, [], "that is not a settings file"
    accepted, ignored = {}, []
    for key, value in body.items():
        if (key not in defaults or SB.is_secret_key(key)
                or not _same_kind(value, defaults[key])):
            ignored.append(str(key))
        else:
            accepted[key] = value
    return accepted, sorted(ignored), ""


def merge(current, accepted):
    """The settings in use with the accepted ones laid over them."""
    merged = dict(current or {})
    merged.update(accepted or {})
    return merged
