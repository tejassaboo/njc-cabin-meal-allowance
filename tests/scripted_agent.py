"""A scripted agent with no LLM, written from the handbook (src/plugin/data/handbook.md) alone: it imports
nothing of the plugin's rules. It follows the step plan through a ``call(tool, arguments)`` function and
returns the submission it would make, so the tests can run each scenario end to end."""

LADDER = ["economy", "premium_economy", "business"]
MEAL_TIMES = {"breakfast": "07:00", "lunch": "12:00", "dinner": "18:00"}


def blocks(segments):
    """C1: lists of (segment, block minutes), cut where a connection is an overnight stop."""
    out, current, minutes = [], [], 0
    for segment in segments:
        current.append(segment)
        minutes += segment["in_air_minutes"]
        after = segment["connection_after"]
        if after is None or after["overnight_stop"]:
            out.append((current, minutes))
            current, minutes = [], 0
        else:
            minutes += after["minutes"]
    return out


def cabin(request, segment, minutes):
    """C2-C5."""
    if request["destination"]["in_canada_or_continental_usa"] or minutes <= 540:
        return "economy"
    return max(segment["cabins_sold"], key=LADDER.index)


def in_status(day, clock):
    """C6: zero-padded HH:MM strings compare correctly as text."""
    start, end = day["status_start_local"] or "00:00", day["status_end_local"] or "23:59"
    return start <= clock <= end


def run(scenario, call):
    """(the tool calls made, in order, as (tool, arguments); the submission)."""
    calls = [("get_trip_request", {"scenario": scenario})]
    request = call(*calls[-1])
    calls.append(("get_allowance_rates", {"rate_location_id": request["destination"]["rate_location_id"]}))
    rates = call(*calls[-1])
    row = next(item for item in rates["rows"] if item["accommodation"] == request["accommodation"])
    cabins, longest = [], 0
    for members, minutes in blocks(request["outbound"]):
        longest = max(longest, minutes)
        cabins += [{"segment_id": segment["segment_id"], "cabin": cabin(request, segment, minutes)} for segment in members]
    meals = sum(
        row[f"{meal}_minor"]
        for day in request["status_days"]
        for meal, clock in MEAL_TIMES.items()
        if in_status(day, clock) and meal not in day["meals_provided"]
    )
    incidentals = len(request["status_days"]) * row["incidental_minor"]
    return calls, {
        "segment_cabins": cabins,
        "longest_continuous_air_minutes": longest,
        "currency": rates["currency"],
        "meal_allowance_minor": meals,
        "incidental_allowance_minor": incidentals,
        "total_minor": meals + incidentals,
    }
