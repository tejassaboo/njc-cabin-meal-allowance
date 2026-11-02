"""The toy world's fixtures: their schema, loader and checks, plus date, clock and minute arithmetic.

Byte-identical in src/plugin/ and verifier/ (a test checks the two copies), so it keeps to the verifier's
pure-stdlib rules: no datetime, no zoneinfo, no os. UTC stamps and minutes are precomputed in the fixtures;
this module only checks that they agree. Every loader raises ValueError on a fixture it cannot trust.
"""

import json
import re

CABINS = ("economy", "premium_economy", "business")  # the ladder, lowest first
MEALS = ("breakfast", "lunch", "dinner")
ACCOMMODATIONS = ("commercial", "private_non_commercial")
APPENDICES = ("appendix_c", "appendix_d")
CURRENCIES = ("CAD", "USD", "EUR", "GBP", "JPY", "KES", "AUD", "MXN")
MAX_STATUS_DAYS = 30  # longer stays (the day-31 and day-121 reductions) are out of scope

IATA = re.compile(r"[A-Z]{3}")
SCENARIO_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
RATE_ID = re.compile(r"[CD](-[A-Z0-9]+)+")
DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
CLOCK = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
LOCAL_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")
UTC_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})Z")


def day_number(date):
    """Days since 1970-01-01 for a valid YYYY-MM-DD date (proleptic Gregorian); ValueError otherwise."""
    match = DATE.fullmatch(date) if isinstance(date, str) else None
    if match is None:
        raise ValueError(f"{date!r} is not a YYYY-MM-DD date")
    year, month, day = (int(part) for part in match.groups())
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    lengths = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if not 1 <= month <= 12 or not 1 <= day <= lengths[month - 1]:
        raise ValueError(f"{date!r} is not a calendar date")
    shifted = year - (month <= 2)
    era = shifted // 400
    year_of_era = shifted - era * 400
    day_of_year = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - 719468


def clock_minutes(clock):
    """Minutes after midnight for an HH:MM clock time; ValueError otherwise."""
    match = CLOCK.fullmatch(clock) if isinstance(clock, str) else None
    if match is None:
        raise ValueError(f"{clock!r} is not an HH:MM clock time")
    return int(match.group(1)) * 60 + int(match.group(2))


def utc_minutes(stamp):
    """Minutes since 1970-01-01T00:00Z for a YYYY-MM-DDTHH:MMZ stamp; ValueError otherwise."""
    match = UTC_STAMP.fullmatch(stamp) if isinstance(stamp, str) else None
    if match is None:
        raise ValueError(f"{stamp!r} is not a YYYY-MM-DDTHH:MMZ stamp")
    return day_number(match.group(1)) * 1440 + clock_minutes(match.group(2))


def local_stamp_ok(stamp):
    match = LOCAL_STAMP.fullmatch(stamp) if isinstance(stamp, str) else None
    if match is None:
        raise ValueError(f"{stamp!r} is not a YYYY-MM-DDTHH:MM stamp")
    day_number(match.group(1))
    clock_minutes(match.group(2))


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path.name}: {error}") from None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def check_rates(rates):
    require(isinstance(rates, dict) and rates, "rates.json must map row ids to rate locations")
    for location_id, location in rates.items():
        require(RATE_ID.fullmatch(location_id) is not None, f"rate id {location_id!r} is malformed")
        require(isinstance(location, dict), f"rate {location_id} must be an object")
        require(location.get("appendix") in APPENDICES, f"rate {location_id}: unknown appendix")
        require(location.get("currency") in CURRENCIES, f"rate {location_id}: unknown currency")
        require(isinstance(location.get("place"), str), f"rate {location_id}: place must be text")
        day_number(location.get("effective_date"))
        rows = location.get("rows")
        require(isinstance(rows, list) and [row.get("accommodation") for row in rows] == list(ACCOMMODATIONS),
                f"rate {location_id}: rows must be commercial then private_non_commercial")
        for row in rows:
            amounts = [row.get(f"{name}_minor") for name in (*MEALS, "meal_total", "incidental")]
            require(all(is_int(amount) and amount > 0 for amount in amounts), f"rate {location_id}: amounts must be positive ints")
            require(sum(amounts[:3]) == amounts[3], f"rate {location_id}: meal total is not breakfast + lunch + dinner")


def check_travellers(travellers):
    require(isinstance(travellers, dict) and travellers, "travellers.json must map ids to travellers")
    for traveller_id, traveller in travellers.items():
        require(isinstance(traveller, dict) and traveller.get("traveller_id") == traveller_id, f"traveller {traveller_id!r} is malformed")
        require(all(isinstance(traveller.get(key), str) for key in ("name", "role")), f"traveller {traveller_id}: name and role must be text")


def load_world(data):
    """{rates, travellers} from the bundled data folder, each checked."""
    rates = read_json(data / "rates.json")
    travellers = read_json(data / "travellers.json")
    check_rates(rates)
    check_travellers(travellers)
    return {"rates": rates, "travellers": travellers}


def check_segments(segments):
    require(isinstance(segments, list) and segments, "outbound must list at least one segment")
    ids = [segment.get("segment_id") if isinstance(segment, dict) else None for segment in segments]
    require(all(isinstance(item, str) and item for item in ids) and len(set(ids)) == len(ids), "segment ids must be unique text")
    for index, segment in enumerate(segments):
        name = segment["segment_id"]
        for key in ("origin", "destination"):
            require(isinstance(segment.get(key), str) and IATA.fullmatch(segment[key]) is not None, f"{name}: {key} is not an IATA code")
        local_stamp_ok(segment.get("depart_local"))
        local_stamp_ok(segment.get("arrive_local"))
        flown = utc_minutes(segment.get("arrive_utc")) - utc_minutes(segment.get("depart_utc"))
        require(is_int(segment.get("in_air_minutes")) and segment["in_air_minutes"] == flown > 0,
                f"{name}: in_air_minutes is not arrive_utc - depart_utc")
        sold = segment.get("cabins_sold")
        require(isinstance(sold, list) and "economy" in sold and all(cabin in CABINS for cabin in sold), f"{name}: cabins_sold must hold economy")
        require(sold == [cabin for cabin in CABINS if cabin in sold], f"{name}: cabins_sold must be unique and lowest first")
        connection = segment.get("connection_after", "missing")
        if index == len(segments) - 1:
            require(connection is None, f"{name}: the last segment has no connection")
            continue
        following = segments[index + 1]
        require(isinstance(connection, dict) and isinstance(connection.get("overnight_stop"), bool), f"{name}: connection is malformed")
        require(following.get("origin") == segment["destination"], f"{name}: the next segment does not leave {segment['destination']}")
        gap = utc_minutes(following.get("depart_utc")) - utc_minutes(segment["arrive_utc"])
        require(is_int(connection.get("minutes")) and connection["minutes"] == gap >= 0,
                f"{name}: connection minutes are not the next departure - this arrival")


def check_days(days):
    require(isinstance(days, list) and 1 <= len(days) <= MAX_STATUS_DAYS, f"status_days must list 1 to {MAX_STATUS_DAYS} days")
    previous = None
    for day in days:
        require(isinstance(day, dict), "a status day must be an object")
        number = day_number(day.get("date"))
        require(previous is None or number == previous + 1, f"{day['date']}: status days must be consecutive")
        previous = number
        start, end = day.get("status_start_local", "missing"), day.get("status_end_local", "missing")
        bounds = [clock_minutes(value) for value in (start, end) if value is not None]
        require(len(bounds) < 2 or bounds[0] <= bounds[1], f"{day['date']}: status ends before it starts")
        provided = day.get("meals_provided")
        require(isinstance(provided, list) and all(meal in MEALS for meal in provided) and len(set(provided)) == len(provided),
                f"{day['date']}: meals_provided must hold distinct meals")


def load_scenario(data, scenario_id):
    """One scenario's facts from data/scenarios/<id>.json, checked for internal consistency."""
    require(isinstance(scenario_id, str) and SCENARIO_ID.fullmatch(scenario_id) is not None, f"{scenario_id!r} is not a scenario id")
    scenario = read_json(data / "scenarios" / f"{scenario_id}.json")
    require(isinstance(scenario, dict) and scenario.get("scenario") == scenario_id, f"scenario file {scenario_id} names another scenario")
    destination = scenario.get("destination")
    require(isinstance(destination, dict) and isinstance(destination.get("in_canada_or_continental_usa"), bool), "destination is malformed")
    require(isinstance(destination.get("rate_location_id"), str), "destination needs a rate_location_id")
    require(scenario.get("accommodation") in ACCOMMODATIONS, "unknown accommodation")
    require(isinstance(scenario.get("request_text"), str), "request_text must be text")
    check_segments(scenario.get("outbound"))
    check_days(scenario.get("status_days"))
    return scenario
