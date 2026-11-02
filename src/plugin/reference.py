from slimconfig import build_output

from contract import NjcEntitlementOutput, ScenarioInput
from plugin.fixtures import scenario, world
from plugin.rules import oracle


def compute_njc_entitlement(given: ScenarioInput) -> NjcEntitlementOutput:
    """The answer key: the one correct entitlement, from the handbook's rules over the bundled fixtures."""
    return build_output(oracle(world(), scenario(given.scenario.value)), NjcEntitlementOutput)
