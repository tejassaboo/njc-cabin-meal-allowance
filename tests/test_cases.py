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
from plugin.rules import oracle

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
    assert 6 <= len(SCENARIOS) <= 8


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
    appendices = {world()["rates"][fact["destination"]["rate_location_id"]]["appendix"] for fact in facts.values()}
    assert appendices == {"appendix_c", "appendix_d"}
    bounds = {(day["status_start_local"], day["status_end_local"]) for fact in facts.values() for day in fact["status_days"]}
    for clock in ("07:00", "18:00"):
        assert any(start == clock for start, _ in bounds)
    for clock in ("12:00", "18:00", "06:59", "11:59", "17:59"):
        assert any(end == clock for _, end in bounds)
    assert any(start == "12:01" for start, _ in bounds)
