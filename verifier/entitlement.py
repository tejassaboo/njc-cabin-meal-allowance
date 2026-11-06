"""The njc-trip-entitlement verdict, and the checks of its reference tool compute_njc_entitlement.

The verifier computes the correct entitlement itself (rules.oracle over the bundled fixtures) and checks the
submitted one against it with a list of constraints with stable ids (the reason codes), in four stages:

0. answer key: the pinned reference equals the verifier's own oracle (else the plugin is broken);
1. referential integrity: segment_cabins names exactly the outbound segments, each once;
2. internal consistency: every cabin is sold on its segment, no amount is negative, the total is the sum;
3. policy decision against the oracle: longest block, cabin per segment, currency, meals, incidentals, total.

Every constraint is checked (each one copes with a submission that failed an earlier stage), so the verdict
grades the whole slip. The message names the first failing constraint in stage order, with the rule and the
numbers, and how many more fail. Shape problems (types, Enum values, missing or extra fields) never get
here: NanoAgent's build_output refuses them first.

``valid`` is strict: true only when every constraint holds, and then the score is 1.0. Otherwise the score is
partial credit for the stage-3 decisions, in hundredths (WEIGHTS, which sum to 100): a right decision earns
its weight, and the cabin weight is shared out per outbound segment (a segment earns its share when it is
named exactly once with the oracle's cabin). Being wrong in either direction costs the same. Two caps keep
it honest: a submission that fails referential integrity (a missing, repeated or unknown segment id) earns
at most INTEGRITY_CAP, and a broken answer key earns 0.0. An empty or all-zero answer can earn only the
currency weight (0.05); another scenario's answer can earn only the cabin and currency weights (0.20), since
every amount and block length is specific to the trip.
"""

from .checks import fixtures, plain, result, scenario_id_of
from .rules import (
    BUSINESS_OVER,
    MEAL_CLOCK,
    block_minutes_by_segment,
    continuous_blocks,
    is_international,
    meal_lines,
    oracle,
    rate_row,
)
from .world import is_int

# build_output guarantees these are ints; the guard keeps a verdict, not an exception, for a host that skips it.
INT_FIELDS = ("longest_continuous_air_minutes", "meal_allowance_minor", "incidental_allowance_minor", "total_minor")

TEXT = {
    "reference-matches-oracle": "The pinned answer key equals the verifier's own oracle",
    "segments-match-journey": "segment_cabins names every outbound segment exactly once, and nothing else",
    "cabins-are-sold": "Every authorized cabin is sold on its segment",
    "amounts-non-negative": "No amount is negative",
    "total-is-sum": "total_minor is meal_allowance_minor + incidental_allowance_minor",
    "longest-block-correct": "longest_continuous_air_minutes is the longest continuous block (C1)",
    "cabins-correct": "Each segment's cabin follows C2-C5",
    "currency-correct": "The currency is the destination row's (C8)",
    "meals-correct": "The meal allowance follows C6-C9",
    "incidentals-correct": "The incidental allowance follows C9",
    "total-correct": "total_minor is the trip's total allowance (C9)",
}
# Hundredths of the score each stage-3 decision earns when it is right; they sum to 100.
WEIGHTS = {
    "cabins-correct": 15,
    "longest-block-correct": 20,
    "currency-correct": 5,
    "meals-correct": 30,
    "incidentals-correct": 20,
    "total-correct": 10,
}
INTEGRITY_CAP = 0.25  # the most a submission that fails segments-match-journey can score


def verify_input(value):
    return result(True, "input is valid")  # a scenario Enum member is all the input there is


def verify_output(input_value, output_value, workspace):
    world, scenario = fixtures(scenario_id_of(input_value))
    key = oracle(world, scenario)
    if plain(output_value) != key:
        return result(False, "compute_njc_entitlement differs from the verifier's oracle", expected=key)
    return result(True, "the answer key matches the verifier's oracle")


def verify_task(arguments, output, reference, workspace):
    world, scenario = fixtures(scenario_id_of(arguments))
    key = oracle(world, scenario)
    pinned = None if reference is None else plain(reference)
    given = plain(output)
    if not isinstance(given, dict) or not isinstance(given.get("segment_cabins"), list):
        raise TypeError("the output is not an entitlement")
    if not all(is_int(given.get(name)) for name in INT_FIELDS):
        raise TypeError("the output's minutes and amounts are not all ints")
    return judge(world, scenario, key, pinned, given)


def judge(world, scenario, key, pinned, given):
    checks = [
        ("reference-matches-oracle", lambda: reference_problem(key, pinned)),
        ("segments-match-journey", lambda: segments_problem(scenario, given)),
        ("cabins-are-sold", lambda: sold_problem(scenario, given)),
        ("amounts-non-negative", lambda: negative_problem(given)),
        ("total-is-sum", lambda: sum_problem(given)),
        ("longest-block-correct", lambda: longest_problem(scenario, key, given)),
        ("cabins-correct", lambda: cabins_problem(scenario, key, given)),
        ("currency-correct", lambda: currency_problem(scenario, key, given)),
        ("meals-correct", lambda: meals_problem(world, scenario, key, given)),
        ("incidentals-correct", lambda: incidentals_problem(world, scenario, key, given)),
        ("total-correct", lambda: total_problem(key, given)),
    ]
    constraints = []
    for identifier, check in checks:
        problem = check()
        constraints.append(entry(identifier, True, None, None, "") if problem is None else entry(identifier, False, *problem))
    failed = [item for item in constraints if item["ok"] is False]
    parts = score_parts(key, given, {item["id"] for item in failed})
    if not failed:
        return result(True, f"the entitlement is correct: {summary(key)}", score=1.0, constraints=constraints, expected=key, score_parts=parts)
    more = f" (+{len(failed) - 1} more)" if len(failed) > 1 else ""
    score = partial_score(parts, {item["id"] for item in failed})
    return result(False, f"{failed[0]['id']}: {failed[0]['message']}{more}", score=score, constraints=constraints, expected=key, score_parts=parts)


def entry(identifier, ok, expected, actual, message):
    return {"id": identifier, "constraint": TEXT[identifier], "ok": ok, "expected": expected, "actual": actual, "message": message}


def score_parts(key, given, failed):
    """Each stage-3 decision's share of the score, in hundredths: its weight when right, else 0; the cabin
    weight shared out over the outbound segments, each earning its share when named once with the right cabin."""
    wanted = cabin_map(key)
    right = sum(1 for segment_id, cabin in wanted.items() if named_cabins(given, segment_id) == [cabin])
    parts = {"cabins-correct": round(WEIGHTS["cabins-correct"] * right / len(wanted), 4)}
    for identifier in ("longest-block-correct", "currency-correct", "meals-correct", "incidentals-correct", "total-correct"):
        parts[identifier] = WEIGHTS[identifier] if identifier not in failed else 0
    return parts


def partial_score(parts, failed):
    """The score of an invalid submission: the earned hundredths, capped when the segment ids are not the
    journey's, and 0.0 when the answer key itself is broken."""
    if "reference-matches-oracle" in failed:
        return 0.0
    score = round(sum(parts.values()) / 100, 4)
    if "segments-match-journey" in failed:
        score = min(score, INTEGRITY_CAP)
    return min(max(score, 0.0), 0.9999)  # never 1.0 for an invalid answer


def summary(key):
    cabins = ", ".join(f"{item['segment_id']} {item['cabin']}" for item in key["segment_cabins"])
    return (
        f"{cabins}; longest block {key['longest_continuous_air_minutes']} min; meals {key['meal_allowance_minor']} + "
        f"incidentals {key['incidental_allowance_minor']} = {key['total_minor']} hundredths {key['currency']}"
    )


def cabin_map(key):
    """segment_id -> cabin of the oracle's answer, whose ids are the journey's, each once."""
    return {item["segment_id"]: item["cabin"] for item in key["segment_cabins"]}


def named_cabins(given, segment_id):
    """The cabins the submission names for one segment id, in order: one for a well-formed answer."""
    return [item["cabin"] for item in given["segment_cabins"] if item["segment_id"] == segment_id]


def reference_problem(key, pinned):
    if pinned is not None and pinned != key:
        return key, pinned, "the pinned answer key differs from the verifier's oracle, so the plugin itself is broken"
    return None


def segments_problem(scenario, given):
    wanted = [segment["segment_id"] for segment in scenario["outbound"]]
    named = [item["segment_id"] for item in given["segment_cabins"]]
    repeated = sorted({item for item in named if named.count(item) > 1})
    unknown = sorted(set(named) - set(wanted))
    missing = [item for item in wanted if item not in named]
    if not (repeated or unknown or missing):
        return None
    parts = (
        ([f"repeated {', '.join(repeated)}"] if repeated else [])
        + ([f"not an outbound segment: {', '.join(unknown)}"] if unknown else [])
        + ([f"missing {', '.join(missing)}"] if missing else [])
    )
    return wanted, sorted(named), "; ".join(parts)


def sold_problem(scenario, given):
    """A named cabin the segment does not sell; ids that are not the journey's are segments-match-journey's."""
    for segment in scenario["outbound"]:
        for cabin in named_cabins(given, segment["segment_id"]):
            if cabin not in segment["cabins_sold"]:
                return segment["cabins_sold"], cabin, (
                    f"{segment['segment_id']} {segment['origin']}-{segment['destination']} sells {', '.join(segment['cabins_sold'])}, not {cabin}"
                )
    return None


def negative_problem(given):
    names = ("meal_allowance_minor", "incidental_allowance_minor", "total_minor", "longest_continuous_air_minutes")
    negative = [name for name in names if given[name] < 0]
    if negative:
        return 0, [given[name] for name in negative], f"negative: {', '.join(f'{name} {given[name]}' for name in negative)}"
    return None


def sum_problem(given):
    meals, incidentals, total = given["meal_allowance_minor"], given["incidental_allowance_minor"], given["total_minor"]
    if total != meals + incidentals:
        return meals + incidentals, total, f"total_minor {total} is not meals {meals} + incidentals {incidentals} = {meals + incidentals}"
    return None


def block_text(scenario):
    """The journey's continuous blocks in words, e.g. 'S1-S2 = 75 + 60 + 405 = 540 min'."""
    segments = {segment["segment_id"]: segment for segment in scenario["outbound"]}
    parts = []
    for block in continuous_blocks(scenario["outbound"]):
        terms = []
        for segment_id in block["segment_ids"]:
            terms.append(str(segments[segment_id]["in_air_minutes"]))
            connection = segments[segment_id]["connection_after"]
            if segment_id != block["segment_ids"][-1]:
                terms.append(f"{connection['minutes']} connection")
        name = block["segment_ids"][0] if len(block["segment_ids"]) == 1 else f"{block['segment_ids'][0]}-{block['segment_ids'][-1]}"
        parts.append(f"{name} = {' + '.join(terms)} = {block['minutes']} min")
    return "; ".join(parts) + (" (cut at an overnight stop)" if len(parts) > 1 else "")


def longest_problem(scenario, key, given):
    wanted, actual = key["longest_continuous_air_minutes"], given["longest_continuous_air_minutes"]
    if actual == wanted:
        return None
    return wanted, actual, f"{actual} min instead of {wanted}: blocks {block_text(scenario)}; ordinary connections count, only an overnight stop cuts"


def cabin_reason(scenario, block_minutes, cabin):
    if not is_international(scenario):
        return "the destination is in Canada or the continental USA (Module 3), so economy"
    if block_minutes <= BUSINESS_OVER:
        return f"its continuous block is {block_minutes} min, not > {BUSINESS_OVER}, so economy"
    if cabin == "business":
        return f"its continuous block is {block_minutes} min > {BUSINESS_OVER} and it sells business"
    return f"its continuous block is {block_minutes} min > {BUSINESS_OVER} but it sells no business, so the highest class it sells, {cabin}"


def cabins_problem(scenario, key, given):
    """The first outbound segment whose cabin is not the oracle's, or that is not named exactly once."""
    wanted = cabin_map(key)
    blocks = block_minutes_by_segment(scenario["outbound"])
    named = sorted(f"{item['segment_id']} {item['cabin']}" for item in given["segment_cabins"])
    for segment in scenario["outbound"]:
        segment_id = segment["segment_id"]
        cabins = named_cabins(given, segment_id)
        where = f"{segment_id} {segment['origin']}-{segment['destination']}"
        if len(cabins) != 1:
            return wanted, named, f"{where} is named {len(cabins)} times, not once; it should be {wanted[segment_id]}"
        if cabins[0] != wanted[segment_id]:
            why = cabin_reason(scenario, blocks[segment_id], wanted[segment_id])
            return wanted, named, f"{where} is {cabins[0]} instead of {wanted[segment_id]}: {why}"
    return None


def currency_problem(scenario, key, given):
    if given["currency"] == key["currency"]:
        return None
    rate_id = scenario["destination"]["rate_location_id"]
    return key["currency"], given["currency"], f"the destination row {rate_id} pays in {key['currency']}, not {given['currency']}"


def meals_problem(world, scenario, key, given):
    wanted, actual = key["meal_allowance_minor"], given["meal_allowance_minor"]
    if actual == wanted:
        return None
    _, row = rate_row(world, scenario)
    lines = meal_lines(world, scenario)
    claimed = "; ".join(f"{line['date']} {'+'.join(line['meals']) or 'none'}" for line in lines)
    clock = ", ".join(f"{meal} {minute // 60:02d}:{minute % 60:02d}" for meal, minute in MEAL_CLOCK.items())
    return wanted, actual, (
        f"{actual} instead of {wanted} hundredths {key['currency']}: claimable meals ({clock}, both status ends included, "
        f"provided meals excluded) are {claimed}, at the {row['accommodation']} row of {scenario['destination']['rate_location_id']}"
    )


def incidentals_problem(world, scenario, key, given):
    wanted, actual = key["incidental_allowance_minor"], given["incidental_allowance_minor"]
    if actual == wanted:
        return None
    _, row = rate_row(world, scenario)
    days = len(scenario["status_days"])
    return wanted, actual, (
        f"{actual} instead of {wanted}: {days} status days (part days count whole) x {row['incidental_minor']} "
        f"({row['accommodation']} row of {scenario['destination']['rate_location_id']}) = {wanted}"
    )


def total_problem(key, given):
    wanted, actual = key["total_minor"], given["total_minor"]
    if actual == wanted:
        return None
    return wanted, actual, f"{actual} instead of {wanted} hundredths {key['currency']}: meals {key['meal_allowance_minor']} + incidentals {key['incidental_allowance_minor']}"
