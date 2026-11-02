"""Checks of get_trip_request: its output must be exactly the bundled scenario's facts."""

from .checks import compared, fixtures, plain, result, scenario_id_of
from .rules import trip_request


def verify_input(value):
    return result(True, "input is valid")  # a scenario Enum member is all the input there is


def verify_output(input_value, output_value, workspace):
    world, scenario = fixtures(scenario_id_of(input_value))
    return compared("get_trip_request", plain(output_value), trip_request(world, scenario))
