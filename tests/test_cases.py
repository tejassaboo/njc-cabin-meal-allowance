"""Every scenario end to end without an LLM: the oracle equals the hand-written expectation, the answer is
unique, and a scripted agent written from the handbook alone reaches it through the tools within the step
budget; each broken variant of its answer fails with the case's reason code."""

import pytest
from helpers import ROOT, SCENARIOS, case, verdict
from scripted_agent import run
from slimconfig import build_output, plain_output

from contract import TOOLS, Currency, NjcCabin, NjcEntitlementOutput, Tool
from plugin import get_allowance_rates, get_trip_request
from plugin.fixtures import scenario as load_scenario
from plugin.fixtures import world
from plugin.rules import continuous_blocks, oracle

IMPLEMENTATIONS = {Tool.GET_TRIP_REQUEST: get_trip_request, Tool.GET_ALLOWANCE_RATES: get_allowance_rates}
MAX_TOOL_CALLS = 4  # plus submit, within the hosted 6 steps whose last may not call tools
AMOUNTS = ("meal_allowance_minor", "incidental_allowance_minor")


def call(tool, arguments):
    """A tool call as NanoAgent makes it: plain JSON in, built into the input class, plain JSON out."""
    given, made = TOOLS[Tool(tool)]
    output = IMPLEMENTATIONS[Tool(tool)](build_output(arguments, given))
    assert isinstance(output, made)
    return plain_output(output)


def test_every_scenario_has_a_case() -> None:
    assert sorted(SCENARIOS) == sorted(path.stem for path in (ROOT / "tests" / "cases").glob("*.json"))
    assert len(SCENARIOS) == 12


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_oracle_equals_the_hand_written_expectation(scenario: str) -> None:
    assert oracle(world(), load_scenario(scenario)) == case(scenario)["expected"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_answer_is_unique(scenario: str) -> None:
    """Exactly one answer passes: any other cabin on any segment, any other currency, and any amount or minute
    count one off (with the total kept consistent) fails; only the order of segment_cabins is free."""
    gold = case(scenario)["expected"]
    assert verdict(scenario, {**gold, "segment_cabins": gold["segment_cabins"][::-1]})["valid"] is True
    for index, item in enumerate(gold["segment_cabins"]):
        for cabin in NjcCabin:
            if cabin.value != item["cabin"]:
                cabins = [dict(entry) for entry in gold["segment_cabins"]]
                cabins[index]["cabin"] = cabin.value
                assert verdict(scenario, {**gold, "segment_cabins": cabins})["valid"] is False
    for currency in Currency:
        if currency.value != gold["currency"]:
            assert verdict(scenario, {**gold, "currency": currency.value})["valid"] is False
    for delta in (-1, 1):
        assert verdict(scenario, {**gold, "longest_continuous_air_minutes": gold["longest_continuous_air_minutes"] + delta})["valid"] is False
        for name in AMOUNTS:
            changed = {**gold, name: gold[name] + delta, "total_minor": gold["total_minor"] + delta}
            assert verdict(scenario, changed)["valid"] is False


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_scripted_agent_reaches_the_gold_answer_within_budget(scenario: str) -> None:
    calls, submission = run(scenario, call)
    assert len(calls) <= MAX_TOOL_CALLS
    assert [tool for tool, _ in calls] == ["get_trip_request", "get_allowance_rates"]
    built = build_output(submission, NjcEntitlementOutput)  # the submit tool's own shape check
    result = verdict(scenario, plain_output(built))
    assert result["valid"] is True, result["message"]
    assert submission == case(scenario)["expected"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_broken_variants_of_the_scripted_answer_fail_with_their_reason(scenario: str) -> None:
    _, submission = run(scenario, call)
    for broken in case(scenario)["broken"]:
        result = verdict(scenario, {**submission, **broken["change"]})
        assert result["valid"] is False and result["message"].split(":")[0] == broken["reason"], (broken["why"], result["message"])


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_request_text_is_flavour_only(scenario: str) -> None:
    """The structured fields alone decide the answer (C10): the oracle ignores request_text, and the scripted
    agent reaches the same submission when the words are blanked out."""
    facts = load_scenario(scenario)
    assert oracle(world(), {**facts, "request_text": ""}) == oracle(world(), facts)

    def muted(tool, arguments):
        output = call(tool, arguments)
        return {**output, "request_text": ""} if tool == "get_trip_request" else output

    assert run(scenario, muted)[1] == run(scenario, call)[1]


def test_the_broken_variants_lead_with_every_reason_code_that_can_lead() -> None:
    """Every reason code heads some bundled broken variant's message, except reference-matches-oracle (a wrong
    pinned key, tested in test_verifier.py) and total-correct, which can never fail first: when the meals and
    the incidentals are right and total-is-sum holds, the total is right too."""
    from verifier.entitlement import TEXT

    leading = {broken["reason"] for scenario in SCENARIOS for broken in case(scenario)["broken"]}
    assert leading == set(TEXT) - {"reference-matches-oracle", "total-correct"}


def test_the_scenarios_cover_the_required_boundaries() -> None:
    """The brief's boundary list, checked against the fixtures themselves."""
    facts = {scenario: load_scenario(scenario) for scenario in SCENARIOS}
    longest = {scenario: oracle(world(), facts[scenario])["longest_continuous_air_minutes"] for scenario in SCENARIOS}
    assert longest["paris-assembly"] == 540 and longest["london-secondment"] == 541
    # 541 only with the connection: the in-air minutes alone are 481.
    assert sum(segment["in_air_minutes"] for segment in facts["london-secondment"]["outbound"]) == 481
    assert facts["nairobi-crop-institute"]["outbound"][0]["connection_after"]["overnight_stop"] is True
    assert facts["nairobi-water-workshop"]["outbound"][0]["connection_after"] == {"minutes": 300, "overnight_stop": False}
    assert "business" not in facts["tokyo-trade-talks"]["outbound"][1]["cabins_sold"]
    # Decision 1575 both ways: Nairobi's overnight stop leaves 505 (economy); Sydney's leaves 1055 (business on S2-S3).
    sydney = facts["sydney-reef-symposium"]["outbound"]
    assert sydney[0]["connection_after"]["overnight_stop"] is True and len(sydney) == 3
    assert [block["minutes"] for block in continuous_blocks(sydney)] == [300, 1055]
    # Berlin: 541 only with the connection (476 in the air); the qualifying long leg sells only economy.
    berlin = facts["berlin-standards-meeting"]["outbound"]
    assert longest["berlin-standards-meeting"] == 541 and sum(segment["in_air_minutes"] for segment in berlin) == 476
    assert berlin[1]["cabins_sold"] == ["economy"] and "business" in berlin[0]["cabins_sold"]
    # Alaska: continental USA (Module 3) on a 620-minute block, Appendix C on the Yukon amounts; Hawaii is Module 4.
    assert facts["anchorage-port-study"]["destination"] == {"city": "Anchorage", "country": "US", "in_canada_or_continental_usa": True, "rate_location_id": "C-ALASKA"}
    assert longest["anchorage-port-study"] == 620 and facts["honolulu-science-meeting"]["destination"]["in_canada_or_continental_usa"] is False
    # Mexico City: an Appendix D row paid in Canadian dollars, private accommodation.
    mexico = facts["mexico-city-census-exchange"]
    assert world()["rates"][mexico["destination"]["rate_location_id"]]["currency"] == "CAD" and mexico["accommodation"] == "private_non_commercial"
    appendices = {world()["rates"][fact["destination"]["rate_location_id"]]["appendix"] for fact in facts.values()}
    assert appendices == {"appendix_c", "appendix_d"}
    assert {world()["rates"][fact["destination"]["rate_location_id"]]["currency"] for fact in facts.values()} == {"EUR", "GBP", "KES", "JPY", "USD", "CAD", "AUD"}
    # The meal clock at each meal's minute and one minute either side, at the start and at the end of status.
    bounds = {(day["status_start_local"], day["status_end_local"]) for fact in facts.values() for day in fact["status_days"]}
    for clock in ("07:00", "07:01", "12:01", "18:00", "18:01"):
        assert any(start == clock for start, _ in bounds), clock
    for clock in ("00:00", "06:59", "07:00", "11:59", "12:00", "12:01", "17:59", "18:00", "18:01"):
        assert any(end == clock for _, end in bounds), clock
