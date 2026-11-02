"""Checks of get_allowance_rates: the id must name a row of the tables, and the output must be that row."""

from .checks import DATA, compared, plain, result
from .rules import rates_view
from .world import RATE_ID, load_world


def requested_id(value):
    given = plain(value)
    if not isinstance(given, dict) or not isinstance(given.get("rate_location_id"), str):
        raise TypeError("the input names no rate_location_id")
    return given["rate_location_id"]


def verify_input(value):
    location_id = requested_id(value)
    if RATE_ID.fullmatch(location_id) is None:
        return result(False, f"{location_id!r} is not an allowance row id such as D-KE-NAIROBI or C-USA")
    if location_id not in load_world(DATA)["rates"]:
        return result(False, f"{location_id!r} is not a row of the allowance tables")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    world = load_world(DATA)
    location_id = requested_id(input_value)
    if location_id not in world["rates"]:
        return result(False, f"{location_id!r} is not a row of the allowance tables")
    return compared("get_allowance_rates", plain(output_value), rates_view(world, location_id))
