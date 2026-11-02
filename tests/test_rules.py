"""The oracle's rules at their boundaries: 540/541 continuous minutes with connections counted, what cuts a
block (an overnight stop, never an ordinary connection however long), per-segment cabins, business not
sold, Module 3 vs 4, the toy meal clock at each meal's minute and one either side, provided meals, part
days, the accommodation row, and the brief's section 11 sanity row (corrected)."""

import pytest

from plugin.fixtures import world
from plugin.rules import (
    BUSINESS_OVER,
    claimable_meals,
    continuous_blocks,
    longest_continuous_minutes,
    oracle,
    segment_cabin,
    segment_cabins,
)

ALL = ["economy", "premium_economy", "business"]


def journey(*parts, sold=None):
    """Segments from (in_air_minutes, connection_minutes or None, overnight_stop) triples; the last has no connection."""
    segments = []
    for index, (minutes, gap, overnight) in enumerate(parts):
        last = index == len(parts) - 1
        segments.append({
            "segment_id": f"S{index + 1}",
            "origin": "AAA",
            "destination": "BBB",
            "in_air_minutes": minutes,
            "cabins_sold": list(sold or ALL),
            "connection_after": None if last else {"minutes": gap, "overnight_stop": overnight},
        })
    return segments


def trip(segments, *, international=True):
    return {"outbound": segments, "destination": {"in_canada_or_continental_usa": not international}}


def cabins(scenario):
    return [item["cabin"] for item in segment_cabins(scenario)]


@pytest.mark.parametrize(("first", "connection", "second", "cabin"), [(75, 60, 405, "economy"), (76, 60, 405, "business"), (75, 61, 405, "business")])
def test_540_does_not_qualify_and_541_does_with_the_connection_counted(first, connection, second, cabin) -> None:
    scenario = trip(journey((first, connection, False), (second, None, False)))
    assert longest_continuous_minutes(scenario) == first + connection + second
    assert cabins(scenario) == [cabin, cabin]


def test_connections_count_toward_continuous_air_travel() -> None:
    # 481 in-air minutes would not qualify on their own; with the 60-minute connection the block is 541.
    scenario = trip(journey((65, 60, False), (416, None, False)))
    assert sum(segment["in_air_minutes"] for segment in scenario["outbound"]) == 481 <= BUSINESS_OVER
    assert longest_continuous_minutes(scenario) == 541
    assert cabins(scenario) == ["business", "business"]


@pytest.mark.parametrize("wait", [0, 90, 300, 720])
def test_an_ordinary_connection_never_cuts_a_block_however_long(wait: int) -> None:
    scenario = trip(journey((300, wait, False), (300, None, False)))
    assert [block["minutes"] for block in continuous_blocks(scenario["outbound"])] == [600 + wait]
    assert cabins(scenario) == ["business", "business"]


@pytest.mark.parametrize("wait", [480, 1615])
def test_an_overnight_stop_cuts_the_block(wait: int) -> None:
    scenario = trip(journey((410, wait, True), (505, None, False)))
    assert [(block["segment_ids"], block["minutes"]) for block in continuous_blocks(scenario["outbound"])] == [(["S1"], 410), (["S2"], 505)]
    assert longest_continuous_minutes(scenario) == 505
    assert cabins(scenario) == ["economy", "economy"]


@pytest.mark.parametrize(("first", "second", "cabins_wanted"), [(540, 541, ["economy", "business"]), (541, 540, ["business", "economy"]), (540, 540, ["economy", "economy"])])
def test_an_overnight_stop_with_a_block_exactly_on_the_threshold(first: int, second: int, cabins_wanted: list) -> None:
    """Each block is judged on its own at exactly 540 / 541: the overnight stop between them changes neither."""
    scenario = trip(journey((first, 600, True), (second, None, False)))
    assert [block["minutes"] for block in continuous_blocks(scenario["outbound"])] == [first, second]
    assert longest_continuous_minutes(scenario) == max(first, second)
    assert cabins(scenario) == cabins_wanted


@pytest.mark.parametrize(
    ("first_sold", "second_sold", "cabins_wanted"),
    [
        (["economy", "premium_economy"], ALL, ["premium_economy", "business"]),
        (ALL, ["economy", "premium_economy"], ["business", "premium_economy"]),
        (["economy"], ALL, ["economy", "business"]),
        (ALL, ["economy"], ["business", "economy"]),
    ],
)
def test_business_not_sold_on_one_leg_of_a_qualifying_block(first_sold, second_sold, cabins_wanted) -> None:
    """Whichever leg lacks business, only that leg drops to the highest class it sells; the other stays business."""
    segments = journey((70, 90, False), (790, None, False))
    segments[0]["cabins_sold"], segments[1]["cabins_sold"] = list(first_sold), list(second_sold)
    scenario = trip(segments)
    assert longest_continuous_minutes(scenario) == 950
    assert cabins(scenario) == cabins_wanted


def test_each_segment_takes_its_own_blocks_cabin() -> None:
    # A divided journey whose second part alone exceeds nine hours: only that part is business.
    scenario = trip(journey((300, 900, True), (420, 100, False), (60, None, False)))
    assert [block["minutes"] for block in continuous_blocks(scenario["outbound"])] == [300, 580]
    assert cabins(scenario) == ["economy", "business", "business"]


@pytest.mark.parametrize(
    ("sold", "cabin"),
    [(ALL, "business"), (["economy", "premium_economy"], "premium_economy"), (["economy"], "economy"), (["economy", "business"], "business")],
)
def test_business_not_sold_falls_to_the_highest_lower_class_sold(sold, cabin) -> None:
    assert segment_cabin(sold, 541, True) == cabin
    assert segment_cabin(sold, 540, True) == "economy"


def test_module_3_is_economy_however_long() -> None:
    scenario = trip(journey((400, 60, False), (400, None, False)), international=False)
    assert longest_continuous_minutes(scenario) == 860
    assert cabins(scenario) == ["economy", "economy"]


def test_cross_policy_sanity_row_njc() -> None:
    """Brief section 11, corrected: leg 360 + 90-minute connection + leg 420 = 870 continuous minutes > 540, so
    business (the connection does not break continuous air travel). With an overnight stop instead, the
    blocks are 360 and 420 and both legs are economy; a domestic trip is economy either way."""
    sanity = journey((360, 90, False), (420, None, False))
    assert longest_continuous_minutes(trip(sanity)) == 870
    assert cabins(trip(sanity)) == ["business", "business"]
    overnight = journey((360, 90, True), (420, None, False))
    assert longest_continuous_minutes(trip(overnight)) == 420
    assert cabins(trip(overnight)) == ["economy", "economy"]
    assert cabins(trip(sanity, international=False)) == ["economy", "economy"]


def day(start, end, provided=()):
    return {"date": "2027-01-01", "status_start_local": start, "status_end_local": end, "meals_provided": list(provided)}


@pytest.mark.parametrize(
    ("start", "meals"),
    [
        ("06:59", ["breakfast", "lunch", "dinner"]),
        ("07:00", ["breakfast", "lunch", "dinner"]),
        ("07:01", ["lunch", "dinner"]),
        ("12:00", ["lunch", "dinner"]),
        ("12:01", ["dinner"]),
        ("18:00", ["dinner"]),
        ("18:01", []),
    ],
)
def test_the_meal_clock_at_the_start_of_status(start, meals) -> None:
    assert claimable_meals(day(start, None)) == meals


@pytest.mark.parametrize(
    ("end", "meals"),
    [
        ("06:59", []),
        ("07:00", ["breakfast"]),
        ("11:59", ["breakfast"]),
        ("12:00", ["breakfast", "lunch"]),
        ("17:59", ["breakfast", "lunch"]),
        ("18:00", ["breakfast", "lunch", "dinner"]),
        ("23:59", ["breakfast", "lunch", "dinner"]),
    ],
)
def test_the_meal_clock_at_the_end_of_status(end, meals) -> None:
    assert claimable_meals(day(None, end)) == meals


def test_a_day_inside_status_and_a_same_day_round_trip() -> None:
    assert claimable_meals(day(None, None)) == ["breakfast", "lunch", "dinner"]
    assert claimable_meals(day("07:00", "18:00")) == ["breakfast", "lunch", "dinner"]
    assert claimable_meals(day("07:01", "17:59")) == ["lunch"]
    assert claimable_meals(day("12:01", "17:59")) == []


@pytest.mark.parametrize(
    ("start", "end", "meals"),
    [
        (None, "00:00", []),  # home at midnight: a part day with no meal, still one incidental (test below)
        ("23:59", None, []),  # leaving at the last minute of the day
        ("00:00", None, ["breakfast", "lunch", "dinner"]),  # status from the first minute of the day
        ("00:00", "23:59", ["breakfast", "lunch", "dinner"]),
        ("18:00", "18:00", ["dinner"]),  # a one-minute status window exactly at a meal time
        ("07:00", "07:00", ["breakfast"]),
    ],
)
def test_the_meal_clock_at_midnight_and_in_one_minute_windows(start, end, meals) -> None:
    assert claimable_meals(day(start, end)) == meals


def test_provided_meals_earn_nothing() -> None:
    assert claimable_meals(day(None, None, ["lunch"])) == ["breakfast", "dinner"]
    assert claimable_meals(day(None, None, ["breakfast", "lunch", "dinner"])) == []
    assert claimable_meals(day("19:00", None, ["dinner"])) == []  # provided outside status changes nothing


def full_trip(rate_id, accommodation, days):
    return {
        "outbound": journey((100, None, False)),
        "destination": {"in_canada_or_continental_usa": rate_id.startswith("C-"), "rate_location_id": rate_id},
        "accommodation": accommodation,
        "status_days": days,
    }


def test_part_days_earn_a_whole_incidental_and_the_accommodation_picks_the_row() -> None:
    days = [day("18:01", None), day(None, None), day(None, "06:59")]  # two part days earn no meal at all
    commercial = oracle(world(), full_trip("D-KE-NAIROBI", "commercial", days))
    private = oracle(world(), full_trip("D-KE-NAIROBI", "private_non_commercial", days))
    assert commercial["meal_allowance_minor"] == private["meal_allowance_minor"] == 203000 + 412500 + 518000
    assert commercial["incidental_allowance_minor"] == 3 * 362720  # 32% of the meal total
    assert private["incidental_allowance_minor"] == 3 * 226700  # 20% of the meal total
    assert commercial["currency"] == private["currency"] == "KES"


def test_a_midnight_arrival_day_earns_an_incidental_but_no_meal() -> None:
    days = [day("06:00", None), day(None, "00:00")]
    key = oracle(world(), full_trip("C-CANADA", "commercial", days))
    assert key["meal_allowance_minor"] == 12320 and key["incidental_allowance_minor"] == 2 * 2500


def test_a_date_line_trip_counts_each_listed_calendar_day_once() -> None:
    """Tokyo: the long leg leaves on the 12th and lands on the 13th local time, so the traveller lives a short
    12th and the fixture lists four calendar days. C6/C9 count the days as listed: four incidentals, and the
    meals of each listed day by its own local clock."""
    from plugin.fixtures import scenario

    facts = scenario("tokyo-no-business")
    assert [day["date"] for day in facts["status_days"]] == ["2027-04-12", "2027-04-13", "2027-04-14", "2027-04-15"]
    assert (facts["outbound"][1]["depart_local"][:10], facts["outbound"][1]["arrive_local"][:10]) == ("2027-04-12", "2027-04-13")
    key = oracle(world(), facts)
    assert key["incidental_allowance_minor"] == 4 * 718720
    assert [claimable_meals(day) for day in facts["status_days"]] == [["breakfast", "lunch"], ["dinner"], ["breakfast", "lunch"], ["breakfast", "lunch"]]


def test_appendix_c_incidentals_do_not_depend_on_accommodation() -> None:
    days = [day(None, None)]
    for rate_id in ("C-CANADA", "C-YUKON", "C-USA"):
        commercial = oracle(world(), full_trip(rate_id, "commercial", days))
        private = oracle(world(), full_trip(rate_id, "private_non_commercial", days))
        assert commercial["incidental_allowance_minor"] == private["incidental_allowance_minor"] == 2500


def test_the_usa_pays_the_canadian_amounts_in_us_dollars() -> None:
    days = [day(None, None)]
    canada = oracle(world(), full_trip("C-CANADA", "commercial", days))
    usa = oracle(world(), full_trip("C-USA", "commercial", days))
    hawaii = oracle(world(), full_trip("D-US-HAWAII", "commercial", days))
    assert canada["total_minor"] == usa["total_minor"] == hawaii["total_minor"] == 12320 + 2500
    assert (canada["currency"], usa["currency"], hawaii["currency"]) == ("CAD", "USD", "USD")


def test_mexico_is_paid_in_canadian_dollars() -> None:
    assert oracle(world(), full_trip("D-MX-MEXICO-CITY", "commercial", [day(None, None)]))["currency"] == "CAD"
