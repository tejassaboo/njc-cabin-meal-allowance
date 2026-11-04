"""The verifier against hand-written submissions (no agent): the brief's section 7 matrix. Correct,
incorrect, missing, consistency and verifier-caught malformed cases run through verify_task; shape
problems are refused by build_output before any verifier runs, exactly as in NanoAgent."""

import json

import pytest
from helpers import SCENARIOS, TASK, arguments, case, reference, verdict
from slimconfig import build_output

import verifier
from contract import NjcEntitlementOutput, RatesInput, ScenarioInput

ORDER = [
    "reference-matches-oracle",
    "segments-match-journey",
    "cabins-are-sold",
    "amounts-non-negative",
    "total-is-sum",
    "longest-block-correct",
    "cabins-correct",
    "currency-correct",
    "meals-correct",
    "incidentals-correct",
]
GOLD_TOKYO = case("tokyo-trade-talks")["expected"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_hand_written_answer_passes(scenario: str) -> None:
    result = verdict(scenario, case(scenario)["expected"])
    assert result["valid"] is True and result["score"] == 1.0, result["message"]
    assert [entry["id"] for entry in result["details"]["constraints"]] == ORDER
    assert all(entry["ok"] is True for entry in result["details"]["constraints"])


@pytest.mark.parametrize(
    ("scenario", "index"), [(scenario, index) for scenario in SCENARIOS for index in range(len(case(scenario)["broken"]))]
)
def test_each_broken_answer_fails_with_its_reason_code(scenario: str, index: int) -> None:
    broken = case(scenario)["broken"][index]
    result = verdict(scenario, {**case(scenario)["expected"], **broken["change"]})
    assert result["valid"] is False and result["score"] == 0.0
    assert result["message"].split(":")[0] == broken["reason"], (broken["why"], result["message"])
    failing = [entry for entry in result["details"]["constraints"] if entry["ok"] is False]
    assert failing[0]["id"] == broken["reason"]


def test_a_failed_stage_leaves_later_stages_unchecked() -> None:
    result = verdict("tokyo-trade-talks", {**GOLD_TOKYO, "segment_cabins": [{"segment_id": "S7", "cabin": "economy"}]})
    states = {entry["id"]: entry["ok"] for entry in result["details"]["constraints"]}
    assert states["segments-match-journey"] is False
    assert all(states[identifier] is None for identifier in ORDER[2:])


def test_messages_name_the_rule_and_the_numbers() -> None:
    paris = case("paris-assembly")["expected"]
    message = verdict("paris-assembly", {**paris, "segment_cabins": [{"segment_id": "S1", "cabin": "business"}, {"segment_id": "S2", "cabin": "business"}]})["message"]
    assert message.startswith("cabins-correct: S1 YYZ-YUL is business instead of economy: its continuous block is 540 min, not > 540")
    message = verdict("paris-assembly", {**paris, "longest_continuous_air_minutes": 480})["message"]
    assert "S1-S2 = 75 + 60 connection + 405 = 540 min" in message
    message = verdict("nairobi-crop-institute", {**case("nairobi-crop-institute")["expected"], "longest_continuous_air_minutes": 915})["message"]
    assert "S1 = 410 = 410 min; S2 = 505 = 505 min (cut at an overnight stop)" in message
    message = verdict("tokyo-trade-talks", {**GOLD_TOKYO, "segment_cabins": [{"segment_id": "S1", "cabin": "business"}, {"segment_id": "S2", "cabin": "economy"}]})["message"]
    assert "950 min > 540 but it sells no business, so the highest class it sells, premium_economy" in message
    message = verdict("whitehorse-site-review", {**case("whitehorse-site-review")["expected"], "segment_cabins": [{"segment_id": "S1", "cabin": "business"}, {"segment_id": "S2", "cabin": "economy"}]})["message"]
    assert "Module 3" in message
    gold = case("washington-conference")["expected"]
    message = verdict("washington-conference", {**gold, "meal_allowance_minor": 21365, "total_minor": 28865})["message"]
    assert "2027-05-06 breakfast" in message and "lunch 12:00" in message
    message = verdict("washington-conference", {**gold, "incidental_allowance_minor": 5000, "total_minor": 23310})["message"]
    assert "3 status days (part days count whole) x 2500" in message


def test_a_message_counts_the_other_failures() -> None:
    changed = {**GOLD_TOKYO, "longest_continuous_air_minutes": 860, "currency": "CAD"}
    result = verdict("tokyo-trade-talks", changed)
    assert result["message"].startswith("longest-block-correct") and result["message"].endswith("(+1 more)")


def test_a_wrong_answer_key_is_caught_before_the_submission() -> None:
    wrong_key = build_output({**GOLD_TOKYO, "currency": "CAD"}, NjcEntitlementOutput)
    result = verifier.verify_task(TASK, arguments("tokyo-trade-talks"), build_output(GOLD_TOKYO, NjcEntitlementOutput), wrong_key, ".")
    assert result["valid"] is False and result["message"].startswith("reference-matches-oracle")


def test_without_a_pinned_reference_the_oracle_still_decides() -> None:
    assert verdict("tokyo-trade-talks", GOLD_TOKYO, pinned=False)["valid"] is True
    assert verdict("tokyo-trade-talks", {**GOLD_TOKYO, "currency": "CAD"}, pinned=False)["valid"] is False


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"segment_cabins": []}, "segments-match-journey"),  # missing: an empty list where entries are required
        ({"segment_cabins": [{"segment_id": "S1", "cabin": "business"}]}, "segments-match-journey"),
        ({"segment_cabins": [{"segment_id": "s1", "cabin": "business"}, {"segment_id": "S2", "cabin": "premium_economy"}]}, "segments-match-journey"),
        ({"meal_allowance_minor": 0, "incidental_allowance_minor": 0, "total_minor": 0}, "meals-correct"),
        ({"meal_allowance_minor": -4774000, "total_minor": -1899120}, "amounts-non-negative"),
        ({"longest_continuous_air_minutes": -950}, "amounts-non-negative"),
        ({"total_minor": 4774000}, "total-is-sum"),
        ({"longest_continuous_air_minutes": 860}, "longest-block-correct"),  # the connection left out
        ({"longest_continuous_air_minutes": 790}, "longest-block-correct"),  # the longest segment alone
        ({"currency": "USD"}, "currency-correct"),
    ],
)
def test_incorrect_missing_and_inconsistent_answers(change: dict, reason: str) -> None:
    result = verdict("tokyo-trade-talks", {**GOLD_TOKYO, **change})
    assert result["valid"] is False and result["message"].split(":")[0] == reason, result["message"]


@pytest.mark.parametrize(
    "raw",
    [
        {**GOLD_TOKYO, "total_minor": "7648880"},  # an amount as a string
        {**GOLD_TOKYO, "total_minor": 7648880.0},  # a float for int hundredths
        {**GOLD_TOKYO, "total_minor": True},
        {**GOLD_TOKYO, "currency": "jpy"},  # wrong case
        {**GOLD_TOKYO, "currency": "YEN"},  # unknown Enum value
        {**GOLD_TOKYO, "segment_cabins": [{"segment_id": "S1", "cabin": "first"}]},  # first is never a cabin here
        {**GOLD_TOKYO, "segment_cabins": [{"segment_id": "S1"}]},  # a nested field missing
        {**GOLD_TOKYO, "segment_cabins": [{"segment_id": "S1", "cabin": "business", "fare": 1}]},  # a nested extra field
        {**GOLD_TOKYO, "segment_cabins": {"S1": "business"}},  # an object, not a list
        {key: value for key, value in GOLD_TOKYO.items() if key != "currency"},  # missing field
        {**GOLD_TOKYO, "notes": "approved"},  # extra field
        {**GOLD_TOKYO, "currency": None},  # null for a non-optional field
        ["business", "premium_economy"],  # not an object
    ],
)
def test_malformed_outputs_are_refused_before_the_verifier(raw) -> None:
    with pytest.raises(ValueError):
        build_output(raw, NjcEntitlementOutput)


def test_non_json_output_never_parses() -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads("{currency: JPY, total_minor: 7648880}")


def cyclic():
    loop = []
    loop.append(loop)
    return loop


@pytest.mark.parametrize(
    ("arguments_value", "output_value"),
    [
        (None, None),
        ("nonsense", 7),
        ({"scenario": "../../etc/passwd"}, GOLD_TOKYO),
        ({"scenario": "no-such-trip"}, GOLD_TOKYO),
        (arguments("tokyo-trade-talks"), None),
        (arguments("tokyo-trade-talks"), {"currency": "JPY"}),
        (arguments("tokyo-trade-talks"), {**GOLD_TOKYO, "segment_cabins": cyclic()}),
        (arguments("tokyo-trade-talks"), {**GOLD_TOKYO, "segment_cabins": [{"segment_id": ["S1"], "cabin": "x"}]}),
        (arguments("tokyo-trade-talks"), {**GOLD_TOKYO, "total_minor": "lots"}),
        (cyclic(), cyclic()),
    ],
)
def test_the_verifier_never_raises(arguments_value, output_value) -> None:
    result = verifier.verify_task(TASK, arguments_value, output_value, None, ".")
    assert result["valid"] is False and result["message"].startswith("verifier-error")
    json.dumps(result)


def mutated_data(tmp_path, change):
    """A copy of the bundled data with one change to the paris-assembly scenario, for the verifier to read."""
    import copy
    import shutil

    from helpers import DATA

    shutil.copytree(DATA, tmp_path / "data")
    facts = json.loads((DATA / "scenarios" / "paris-assembly.json").read_text(encoding="utf-8"))
    facts = copy.deepcopy(facts)
    change(facts)
    (tmp_path / "data" / "scenarios" / "paris-assembly.json").write_text(json.dumps(facts), encoding="utf-8")
    return tmp_path / "data"


def thirty_one_days(facts):
    facts["status_days"] = [
        {"date": f"2027-01-{day:02d}", "status_start_local": "08:00" if day == 1 else None, "status_end_local": "20:00" if day == 31 else None, "meals_provided": []}
        for day in range(1, 32)
    ]


def unknown_destination_row(facts):
    facts["destination"]["rate_location_id"] = "D-XX-ATLANTIS"


@pytest.mark.parametrize(("change", "needle"), [(thirty_one_days, "1 to 30 days"), (unknown_destination_row, "D-XX-ATLANTIS")])
def test_a_stay_over_30_days_or_an_unknown_destination_is_a_verifier_error_not_an_exception(tmp_path, monkeypatch, change, needle) -> None:
    """Long stays are out of scope (the day-31 reductions are conditional in v326), so the loader refuses such a
    fixture; the verifier turns that, and a destination row the tables do not hold, into a failed verdict."""
    import verifier.checks

    monkeypatch.setattr(verifier.checks, "DATA", mutated_data(tmp_path, change))
    gold = build_output(case("paris-assembly")["expected"], NjcEntitlementOutput)
    for result in (
        verifier.verify_task(TASK, arguments("paris-assembly"), gold, None, "."),
        verifier.verify_output("compute_njc_entitlement", arguments("paris-assembly"), gold, "."),
    ):
        assert result["valid"] is False and result["score"] == 0.0
        assert result["message"].startswith("verifier-error") and needle in result["message"], result["message"]
        json.dumps(result)
    # get_trip_request never reads the rate table, so only the loader's refusals reach it; either way no exception.
    result = verifier.verify_output("get_trip_request", arguments("paris-assembly"), gold, ".")
    assert result["valid"] is False
    json.dumps(result)


def test_an_unknown_task_or_tool_id_is_a_failed_verdict_not_an_exception() -> None:
    gold = build_output(GOLD_TOKYO, NjcEntitlementOutput)
    for result in (
        verifier.verify_task("book-trip", arguments("tokyo-trade-talks"), gold, None, "."),
        verifier.verify_task(None, arguments("tokyo-trade-talks"), gold, None, "."),
        verifier.verify_input("search", arguments("tokyo-trade-talks")),
        verifier.verify_input(["get_trip_request"], None),
        verifier.verify_output("search", None, None, "."),
        verifier.verify_output("get_allowance_rates", None, None, "."),
        verifier.verify_output("get_trip_request", cyclic(), cyclic(), "."),
    ):
        assert result["valid"] is False and result["message"].startswith("verifier-error")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_verdicts_are_deterministic_plain_json(scenario: str) -> None:
    broken = {**case(scenario)["expected"], **case(scenario)["broken"][0]["change"]}
    for output in (case(scenario)["expected"], broken):
        first, second = verdict(scenario, output), verdict(scenario, output)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)  # no default=: plain JSON only
        assert isinstance(first["score"], float) and 0.0 <= first["score"] <= 1.0


@pytest.mark.parametrize(
    ("raw", "valid"),
    [
        ({"rate_location_id": "D-KE-NAIROBI"}, True),
        ({"rate_location_id": "C-YUKON"}, True),
        ({"rate_location_id": "D-XX-ATLANTIS"}, False),
        ({"rate_location_id": "d-ke-nairobi"}, False),
        ({"rate_location_id": ""}, False),
        ({"rate_location_id": "../rates"}, False),
    ],
)
def test_rates_input_checks(raw: dict, valid: bool) -> None:
    assert verifier.verify_input("get_allowance_rates", build_output(raw, RatesInput))["valid"] is valid


def test_the_reference_tool_output_is_checked_against_the_oracle() -> None:
    good = verifier.verify_output("compute_njc_entitlement", arguments("paris-assembly"), reference("paris-assembly"), ".")
    bad = verifier.verify_output("compute_njc_entitlement", arguments("paris-assembly"), reference("london-secondment"), ".")
    assert good["valid"] is True and bad["valid"] is False
    assert verifier.verify_input("compute_njc_entitlement", build_output({"scenario": "paris-assembly"}, ScenarioInput))["valid"] is True


@pytest.mark.parametrize("raw", [{**GOLD_TOKYO, "total_minor": 7648880.0}, {**GOLD_TOKYO, "meal_allowance_minor": "4774000"}])
def test_a_plain_output_with_a_non_int_amount_is_a_verifier_error_not_a_pass(raw) -> None:
    """The host builds the output first, so this never happens in a run; a host that skipped it still gets a verdict."""
    result = verifier.verify_task(TASK, arguments("tokyo-trade-talks"), raw, None, ".")
    assert result["valid"] is False and result["message"].startswith("verifier-error")
    json.dumps(result)
