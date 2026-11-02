"""The tools: what they return, what they refuse, how big their outputs are, and the real MCP server."""

import json
import sys

import anyio
import pytest
from helpers import ROOT, SCENARIOS
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output, plain_output

import verifier
from contract import RatesInput, ScenarioInput, TripRequestOutput
from plugin import get_allowance_rates, get_trip_request
from plugin.fixtures import world

MAX_OUTPUT_CHARS = 4000  # about 1k tokens: every tool output stays far from the hosted 65,536-token budget


def trip(scenario):
    return get_trip_request(build_output({"scenario": scenario}, ScenarioInput))


def rates(location_id):
    return get_allowance_rates(build_output({"rate_location_id": location_id}, RatesInput))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_tool_outputs_match_the_fixtures_and_stay_small(scenario: str) -> None:
    given = build_output({"scenario": scenario}, ScenarioInput)
    request = trip(scenario)
    assert verifier.verify_output("get_trip_request", given, request, ".")["valid"] is True
    assert len(json.dumps(plain_output(request))) <= MAX_OUTPUT_CHARS
    query = build_output({"rate_location_id": request.destination.rate_location_id}, RatesInput)
    row = get_allowance_rates(query)
    assert verifier.verify_input("get_allowance_rates", query)["valid"] is True
    assert verifier.verify_output("get_allowance_rates", query, row, ".")["valid"] is True
    assert len(json.dumps(plain_output(row))) <= MAX_OUTPUT_CHARS


@pytest.mark.parametrize("location_id", sorted(world()["rates"]))
def test_every_rate_row_is_served_with_both_accommodation_types(location_id: str) -> None:
    row = rates(location_id)
    assert [item.accommodation.value for item in row.rows] == ["commercial", "private_non_commercial"]
    assert row.effective_date == "2026-10-01"


@pytest.mark.parametrize("location_id", ["D-XX-ATLANTIS", "d-ke-nairobi", ""])
def test_an_unknown_rate_row_is_refused(location_id: str) -> None:
    with pytest.raises(ValueError, match="not an allowance row"):
        rates(location_id)


def test_a_changed_tool_output_is_caught() -> None:
    given = build_output({"scenario": "paris-assembly"}, ScenarioInput)
    original = plain_output(trip("paris-assembly"))
    original["outbound"][0]["connection_after"]["overnight_stop"] = True
    result = verifier.verify_output("get_trip_request", given, build_output(original, TripRequestOutput), ".")
    assert result["valid"] is False and "outbound" in result["message"]
    query = build_output({"rate_location_id": "C-YUKON"}, RatesInput)
    result = verifier.verify_output("get_allowance_rates", query, rates("C-CANADA"), ".")
    assert result["valid"] is False


def test_the_mcp_server_serves_every_tool() -> None:
    async def session():
        server = StdioServerParameters(command=sys.executable, args=["-m", "plugin"], cwd=str(ROOT))
        async with stdio_client(server) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            names = sorted(tool.name for tool in (await client.list_tools()).tools)
            answer = await client.call_tool("get_trip_request", {"scenario": "tokyo-trade-talks"})
            row = await client.call_tool("get_allowance_rates", {"rate_location_id": "D-JP-TOKYO"})
            refused = await client.call_tool("get_allowance_rates", {"rate_location_id": "D-XX-ATLANTIS"})
            return names, answer, row, refused

    names, answer, row, refused = anyio.run(session)
    assert names == ["compute_njc_entitlement", "get_allowance_rates", "get_trip_request"]
    assert answer.isError is False and answer.structuredContent["destination"]["rate_location_id"] == "D-JP-TOKYO"
    assert row.isError is False and row.structuredContent["currency"] == "JPY"
    assert refused.isError is True
