from slimconfig import build_output

from contract import RatesInput, RatesOutput
from plugin.fixtures import world
from plugin.rules import rates_view


def get_allowance_rates(given: RatesInput) -> RatesOutput:
    """One Appendix C or D allowance row (days 1-30), both accommodation types. It applies no policy."""
    if given.rate_location_id not in world()["rates"]:
        known = ", ".join(sorted(world()["rates"]))
        raise ValueError(f"{given.rate_location_id!r} is not an allowance row; known rows: {known}")
    return build_output(rates_view(world(), given.rate_location_id), RatesOutput)
