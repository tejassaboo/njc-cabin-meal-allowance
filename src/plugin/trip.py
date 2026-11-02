from slimconfig import build_output

from contract import ScenarioInput, TripRequestOutput
from plugin.fixtures import scenario, world
from plugin.rules import trip_request


def get_trip_request(given: ScenarioInput) -> TripRequestOutput:
    """The scenario's trip: the traveller's words and the structured facts, never an answer."""
    return build_output(trip_request(world(), scenario(given.scenario.value)), TripRequestOutput)
