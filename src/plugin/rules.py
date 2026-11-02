"""The NJC Travel Directive (v326) as this plugin's toy handbook states it (src/plugin/data/handbook.md): the
oracle that the reference tool and the verifier both run on the bundled fixtures.

Byte-identical in src/plugin/ and verifier/ (a test checks the two copies), so it keeps to the verifier's
pure-stdlib rules. Every function is a pure function of the fixtures and one scenario. Money is int
hundredths of the row's currency throughout; nothing is ever rounded because nothing is ever divided.
"""

from .world import CABINS, MEALS, clock_minutes

BUSINESS_OVER = 540  # continuous air travel must exceed this many minutes (nine hours) for business (rule 3, C2)
MEAL_CLOCK = {"breakfast": 7 * 60, "lunch": 12 * 60, "dinner": 18 * 60}  # toy meal times, minutes after midnight (C6)
DAY_START, DAY_END = 0, 23 * 60 + 59  # a null status bound means the status spans that end of the day


def trip_request(world, scenario):
    """The trip request get_trip_request shows: the scenario's facts with its traveller."""
    return {
        "scenario": scenario["scenario"],
        "request_text": scenario["request_text"],
        "traveller": dict(world["travellers"][scenario["traveller_id"]]),
        "destination": dict(scenario["destination"]),
        "accommodation": scenario["accommodation"],
        "outbound": [dict(segment) for segment in scenario["outbound"]],
        "status_days": [dict(day) for day in scenario["status_days"]],
    }


def rates_view(world, rate_location_id):
    """The allowance row get_allowance_rates shows; KeyError for an id the tables do not hold."""
    location = world["rates"][rate_location_id]
    return {"rate_location_id": rate_location_id, **{key: location[key] for key in ("appendix", "place", "currency", "effective_date", "rows")}}


def is_international(scenario):
    """Module 4 (international travel) applies when the destination is outside Canada and the continental USA."""
    return not scenario["destination"]["in_canada_or_continental_usa"]


def continuous_blocks(segments):
    """The journey cut at every overnight stop: [{segment_ids, minutes}] in flying order.

    A block runs from its first segment's scheduled departure to its last segment's scheduled arrival, so
    its minutes are its segments' in-air minutes plus the ordinary connections between them (C1).
    """
    blocks, current = [], {"segment_ids": [], "minutes": 0}
    for segment in segments:
        current["segment_ids"].append(segment["segment_id"])
        current["minutes"] += segment["in_air_minutes"]
        connection = segment["connection_after"]
        if connection is None or connection["overnight_stop"]:
            blocks.append(current)
            current = {"segment_ids": [], "minutes": 0}
        else:
            current["minutes"] += connection["minutes"]
    return blocks


def block_minutes_by_segment(segments):
    """segment_id -> the minutes of the continuous block that segment belongs to."""
    return {segment_id: block["minutes"] for block in continuous_blocks(segments) for segment_id in block["segment_ids"]}


def segment_cabin(cabins_sold, block_minutes, international):
    """The cabin authorized on one segment (rule 3, C2-C4).

    Business when the trip is international and the segment's block exceeds BUSINESS_OVER minutes; if the
    flight does not sell business, the highest class it sells below business. Economy otherwise.
    """
    if international and block_minutes > BUSINESS_OVER:
        for cabin in reversed(CABINS):
            if cabin in cabins_sold:
                return cabin
    return "economy"


def segment_cabins(scenario):
    """[{segment_id, cabin}] in flying order."""
    blocks = block_minutes_by_segment(scenario["outbound"])
    international = is_international(scenario)
    return [
        {"segment_id": segment["segment_id"], "cabin": segment_cabin(segment["cabins_sold"], blocks[segment["segment_id"]], international)}
        for segment in scenario["outbound"]
    ]


def longest_continuous_minutes(scenario):
    return max(block["minutes"] for block in continuous_blocks(scenario["outbound"]))


def on_status_at(day, minute):
    """Travel status covers this clock minute of the day: start <= minute <= end, both ends included (C6)."""
    start = DAY_START if day["status_start_local"] is None else clock_minutes(day["status_start_local"])
    end = DAY_END if day["status_end_local"] is None else clock_minutes(day["status_end_local"])
    return start <= minute <= end


def claimable_meals(day):
    """The meals of one status day that earn an allowance, in meal order: on status at the meal's toy clock time
    and not provided (C6, C7)."""
    return [meal for meal in MEALS if on_status_at(day, MEAL_CLOCK[meal]) and meal not in day["meals_provided"]]


def rate_row(world, scenario):
    """(the destination's rate location, the row for the scenario's accommodation) (C8, C9)."""
    location = world["rates"][scenario["destination"]["rate_location_id"]]
    row = next(row for row in location["rows"] if row["accommodation"] == scenario["accommodation"])
    return location, row


def meal_lines(world, scenario):
    """[{date, meals, minor}] per status day: the claimable meals and their allowance."""
    _, row = rate_row(world, scenario)
    lines = []
    for day in scenario["status_days"]:
        meals = claimable_meals(day)
        lines.append({"date": day["date"], "meals": meals, "minor": sum(row[f"{meal}_minor"] for meal in meals)})
    return lines


def oracle(world, scenario):
    """The one correct entitlement for ``scenario``, as the task output's plain JSON."""
    location, row = rate_row(world, scenario)
    meals = sum(line["minor"] for line in meal_lines(world, scenario))
    incidentals = len(scenario["status_days"]) * row["incidental_minor"]
    return {
        "segment_cabins": segment_cabins(scenario),
        "longest_continuous_air_minutes": longest_continuous_minutes(scenario),
        "currency": location["currency"],
        "meal_allowance_minor": meals,
        "incidental_allowance_minor": incidentals,
        "total_minor": meals + incidentals,
    }
