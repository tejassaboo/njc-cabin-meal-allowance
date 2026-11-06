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
    "total-correct",
]
GOLD_TOKYO = case("tokyo-trade-talks")["expected"]
LAZY = {"segment_cabins": [], "longest_continuous_air_minutes": 0, "currency": "CAD", "meal_allowance_minor": 0, "incidental_allowance_minor": 0, "total_minor": 0}


def score_of(scenario, output):
    result = verdict(scenario, output)
    assert isinstance(result["score"], float) and 0.0 <= result["score"] <= 1.0
    assert result["valid"] is (result["score"] == 1.0)  # valid stays strict: full marks only when everything is right
    return result["score"]


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
    assert result["valid"] is False and 0.0 <= result["score"] < 1.0
    assert result["message"].split(":")[0] == broken["reason"], (broken["why"], result["message"])
    failing = [entry for entry in result["details"]["constraints"] if entry["ok"] is False]
    assert failing[0]["id"] == broken["reason"]


def test_every_constraint_is_checked_and_the_first_failure_is_reported_in_stage_order() -> None:
    """A submission naming a segment the journey does not have: integrity fails, the sold check skips the unknown
    id, and the decision checks still run (so partial credit can be graded) without raising."""
    result = verdict("tokyo-trade-talks", {**GOLD_TOKYO, "segment_cabins": [{"segment_id": "S7", "cabin": "economy"}]})
    states = {entry["id"]: entry["ok"] for entry in result["details"]["constraints"]}
    assert all(isinstance(state, bool) for state in states.values())
    assert states["segments-match-journey"] is False and states["cabins-are-sold"] is True and states["cabins-correct"] is False
    assert all(states[identifier] is True for identifier in ("longest-block-correct", "currency-correct", "meals-correct", "incidentals-correct", "total-correct"))
    assert result["message"].startswith("segments-match-journey: not an outbound segment: S7; missing S1, S2 (+1 more)")
    assert result["score"] == 0.25  # every amount is right, but the integrity failure caps the score


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_gold_answer_scores_one_and_its_parts_sum_to_a_hundred(scenario: str) -> None:
    result = verdict(scenario, case(scenario)["expected"])
    assert result["score"] == 1.0
    assert sum(result["details"]["score_parts"].values()) == 100


def test_partial_credit_is_proportional_to_what_is_right() -> None:
    tokyo = GOLD_TOKYO
    # One of two cabins wrong (business where only premium economy is sold): half the 15-hundredth cabin weight.
    assert score_of("tokyo-trade-talks", {**tokyo, "segment_cabins": [{"segment_id": "S1", "cabin": "business"}, {"segment_id": "S2", "cabin": "business"}]}) == 0.925
    # Both cabins wrong: the whole cabin weight.
    assert score_of("tokyo-trade-talks", {**tokyo, "segment_cabins": [{"segment_id": "S1", "cabin": "economy"}, {"segment_id": "S2", "cabin": "economy"}]}) == 0.85
    # The longest block wrong (connection left out), cabins right: the 20-hundredth block weight.
    assert score_of("tokyo-trade-talks", {**tokyo, "longest_continuous_air_minutes": 860}) == 0.8
    # The currency alone: 5 hundredths.
    assert score_of("tokyo-trade-talks", {**tokyo, "currency": "CAD"}) == 0.95
    # Meals wrong with a consistent total: meals (30) and total (10).
    assert score_of("tokyo-trade-talks", {**tokyo, "meal_allowance_minor": 4774001, "total_minor": 7648881}) == 0.6
    # Incidentals wrong with a consistent total: incidentals (20) and total (10).
    assert score_of("tokyo-trade-talks", {**tokyo, "incidental_allowance_minor": 2874881, "total_minor": 7648881}) == 0.7
    # Meals and incidentals swapped: the total survives, 10 of the 60 money hundredths.
    paris = case("paris-assembly")["expected"]
    assert score_of("paris-assembly", {**paris, "meal_allowance_minor": 15704, "incidental_allowance_minor": 20020}) == 0.5
    # One of three segments wrong on the three-segment journey: cabin credit in thirds (15 x 2/3 = 10).
    sydney = case("sydney-reef-symposium")["expected"]
    one_wrong = [dict(item) for item in sydney["segment_cabins"]]
    one_wrong[0]["cabin"] = "business"
    assert score_of("sydney-reef-symposium", {**sydney, "segment_cabins": one_wrong}) == 0.95


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("name", ["meal_allowance_minor", "incidental_allowance_minor", "longest_continuous_air_minutes"])
def test_too_high_and_too_low_score_the_same(scenario: str, name: str) -> None:
    gold = case(scenario)["expected"]
    scores = []
    for delta in (-1, 1):
        changed = {**gold, name: gold[name] + delta}
        if name != "longest_continuous_air_minutes":
            changed["total_minor"] = gold["total_minor"] + delta
        scores.append(score_of(scenario, changed))
    assert scores[0] == scores[1] < 1.0


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_lazy_answers_score_at_or_near_zero(scenario: str) -> None:
    """An empty, all-zero slip can earn only the currency weight (0.05) when CAD happens to be right."""
    assert score_of(scenario, LAZY) <= 0.05
    gold = case(scenario)["expected"]
    economy = [{"segment_id": item["segment_id"], "cabin": "economy"} for item in gold["segment_cabins"]]
    zeros = {**gold, "segment_cabins": economy, "longest_continuous_air_minutes": 0, "meal_allowance_minor": 0, "incidental_allowance_minor": 0, "total_minor": 0}
    assert score_of(scenario, zeros) <= 0.2  # at most the cabin and currency weights, when economy is right


def test_another_scenarios_answer_scores_low() -> None:
    """Every amount is specific to the trip, so a cross-scenario answer earns little: the cabin and currency weights
    when they coincide (0.20), the integrity cap (0.25) when the segment count differs, and 0.275 for London's
    answer on Berlin, whose blocks are both 541 by design (the 540/541 straddle) and share one cabin."""
    scores = {}
    for scenario in SCENARIOS:
        for other in SCENARIOS:
            if other != scenario:
                scores[(scenario, other)] = score_of(scenario, case(other)["expected"])
    assert max(scores.values()) == 0.275
    assert {pair for pair, score in scores.items() if score > 0.25} == {("london-secondment", "berlin-standards-meeting"), ("berlin-standards-meeting", "london-secondment")}
    assert sum(score <= 0.2 for score in scores.values()) >= len(scores) - 4


def test_an_integrity_failure_caps_the_score() -> None:
    """Right amounts with an extra, repeated or missing segment id: at most INTEGRITY_CAP (documented in the README)."""
    extra = {**GOLD_TOKYO, "segment_cabins": [*GOLD_TOKYO["segment_cabins"], {"segment_id": "S9", "cabin": "economy"}]}
    assert score_of("tokyo-trade-talks", extra) == 0.25
    repeated = {**GOLD_TOKYO, "segment_cabins": [GOLD_TOKYO["segment_cabins"][0], *GOLD_TOKYO["segment_cabins"]]}
    assert score_of("tokyo-trade-talks", repeated) == 0.25
    missing = {**GOLD_TOKYO, "segment_cabins": GOLD_TOKYO["segment_cabins"][:1]}
    assert score_of("tokyo-trade-talks", missing) == 0.25
    # The cap only lowers: an answer that is also wrong on the money earns min(its credit, the cap).
    assert score_of("tokyo-trade-talks", {**extra, "meal_allowance_minor": 0, "total_minor": 2874880}) == 0.25  # 0.60 capped
    assert score_of("tokyo-trade-talks", {**extra, "currency": "CAD", "longest_continuous_air_minutes": 1, "meal_allowance_minor": 0, "incidental_allowance_minor": 0, "total_minor": 0}) == 0.15
    assert score_of("tokyo-trade-talks", LAZY) == 0.0


def test_a_broken_answer_key_scores_zero() -> None:
    wrong_key = build_output({**GOLD_TOKYO, "currency": "CAD"}, NjcEntitlementOutput)
    result = verifier.verify_task(TASK, arguments("tokyo-trade-talks"), build_output(GOLD_TOKYO, NjcEntitlementOutput), wrong_key, ".")
    assert result["valid"] is False and result["score"] == 0.0


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
