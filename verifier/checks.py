"""Shared verdict helpers: a result, plain JSON forms of the contract instances, and the bundled
fixtures read from the plugin folder. Pure functions of their arguments and the files on disk."""

import dataclasses
from enum import Enum
from pathlib import Path

from .world import load_scenario, load_world

DATA = Path(__file__).resolve().parents[1] / "src" / "plugin" / "data"
MAX_DEPTH = 32  # contract values are a few levels deep; anything deeper, or cyclic, is refused


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def plain(value, depth=0):
    """A contract instance (or anything inside one) as plain JSON values, Enum members as their values.

    Raises ValueError for anything that is not a contract value, or that nests deeper than MAX_DEPTH (which
    also stops a cyclic structure); the entry points turn that into a failed verdict.
    """
    if depth > MAX_DEPTH:
        raise ValueError("value nests too deeply, or is cyclic")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return plain(dataclasses.asdict(value), depth + 1)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {plain(key, depth + 1): plain(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item, depth + 1) for item in value]
    if value is None or isinstance(value, (str, int, float)):
        return value
    raise TypeError(f"{type(value)!r} is not a contract value")


def fixtures(scenario_id):
    """(the toy world, the scenario's facts), from the plugin's bundled data."""
    return load_world(DATA), load_scenario(DATA, scenario_id)


def scenario_id_of(arguments):
    given = plain(arguments)
    if not isinstance(given, dict) or not isinstance(given.get("scenario"), str):
        raise TypeError("the arguments name no scenario")
    return given["scenario"]


def compared(name, given, wanted):
    """A verify_output verdict: the tool's output equals what the fixtures give, or the keys that differ."""
    if given == wanted:
        return result(True, f"{name} output matches the bundled fixtures")
    if not isinstance(given, dict):
        return result(False, f"{name} output is not an object")
    different = sorted(str(key) for key in set(given) | set(wanted) if given.get(key) != wanted.get(key))
    return result(False, f"{name} output differs from the bundled fixtures at {', '.join(different)}")
