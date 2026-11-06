"""The environment: the vendored copies stay identical, the handbook is the task's instructions, the
generator reproduces the committed fixtures, the rates are the source's printed amounts, and the fixtures
hold their invariants (UTC recomputed here with zoneinfo, which the plugin never uses at evaluation time)."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from helpers import DATA, ROOT, SCENARIOS

from plugin.fixtures import scenario as load_scenario
from plugin.fixtures import world
from plugin.tools_dev.generate import files
from plugin.world import load_scenario as load_scenario_from
from plugin.world import load_world

# Appendix C/D (effective 2026-10-01), days 1-30, as printed: breakfast, lunch, dinner, meal total, commercial
# incidental, private incidental, in hundredths. Typed in from the source, independently of generate.py.
SOURCE_ROWS = {
    "C-CANADA": ("CAD", 2995, 3055, 6270, 12320, 2500, 2500),
    "C-YUKON": ("CAD", 2735, 3470, 8130, 14335, 2500, 2500),
    "C-NWT": ("CAD", 2930, 3475, 7415, 13820, 2500, 2500),
    "C-NUNAVUT": ("CAD", 3555, 4220, 10190, 17965, 2500, 2500),
    "C-USA": ("USD", 2995, 3055, 6270, 12320, 2500, 2500),
    "C-ALASKA": ("USD", 2735, 3470, 8130, 14335, 2500, 2500),  # "Alaska follows the Yukon rates", in US funds
    "D-DE-BERLIN": ("EUR", 2865, 4435, 6045, 13345, 4270, 2669),
    "D-AU-SYDNEY": ("AUD", 4480, 8500, 11615, 24595, 7870, 4919),
    "D-FR-PARIS": ("EUR", 2490, 4520, 5260, 12270, 3926, 2454),
    "D-GB-LONDON": ("GBP", 2335, 4085, 4625, 11045, 3534, 2209),
    "D-KE-NAIROBI": ("KES", 203000, 412500, 518000, 1133500, 362720, 226700),
    "D-JP-TOKYO": ("JPY", 604000, 660000, 982000, 2246000, 718720, 449200),
    "D-US-HAWAII": ("USD", 2995, 3055, 6270, 12320, 2500, 2500),
    "D-MX-MEXICO-CITY": ("CAD", 3315, 6545, 8410, 18270, 5846, 3654),
}


@pytest.mark.parametrize("module", ["rules.py", "world.py"])
def test_the_verifier_runs_the_same_code(module: str) -> None:
    assert (ROOT / "verifier" / module).read_bytes() == (ROOT / "src" / "plugin" / module).read_bytes()


def instructions(manifest_text):
    """The task's instructions: the `|-` block scalar under it, unindented."""
    lines = manifest_text.split("\n")
    start = lines.index("    instructions: |-") + 1
    block = []
    for line in lines[start:]:
        if line and not line.startswith("      "):
            break
        block.append(line[6:])
    return "\n".join(block).rstrip("\n")


def test_the_handbook_is_the_task_instructions() -> None:
    handbook = (DATA / "handbook.md").read_text(encoding="utf-8")
    assert instructions((ROOT / "nanoagent.yaml").read_text(encoding="utf-8")) == handbook.rstrip("\n")
    assert len(handbook.split()) <= 1500


def test_the_handbook_pins_its_source_and_states_the_toy_rules() -> None:
    handbook = (DATA / "handbook.md").read_text(encoding="utf-8")
    for needle in (
        "## Clarifications (toy rules)",
        "## Rules not in scope",
        "version 326",
        "6fd931c9d361d5300f586ae7918a9b7719d296c395abd2cefea82fc98775af1b",
        "46cde1bb3e85f5e99eea2989b9c6f38bc20883229603a0333a5766fa72377a49",
        "9a96123b14894e80af3095e665b33042b3f451b32511a88f98bca7de24a40661",
        "8f9772b345811d53a51f5016e4017b7275f17362912ebcef0a550d396316615d",
        "Source drift",
        "2026-11-06",
        "October 1, 2026",
        "decision 1575",
        "more than 540 minutes",
        "07:00",
        "12:00",
        "18:00",
        "Alaska counts as continental USA",
        "rule 4 allows any lower class",
        "the date line",
    ):
        assert needle in handbook, needle


def test_appendix_c_and_d_rows_are_typed_as_the_source_files_them() -> None:
    """Appendix C: Canada, the territories and the USA, Alaska included; Appendix D: everything else, Hawaii included."""
    appendices = {location_id: location["appendix"] for location_id, location in world()["rates"].items()}
    assert all(appendix == ("appendix_c" if location_id.startswith("C-") else "appendix_d") for location_id, appendix in appendices.items())
    assert appendices["C-ALASKA"] == "appendix_c" and appendices["D-US-HAWAII"] == "appendix_d"
    assert world()["rates"]["C-ALASKA"]["rows"][0]["meal_total_minor"] == world()["rates"]["C-YUKON"]["rows"][0]["meal_total_minor"]
    assert world()["rates"]["D-US-HAWAII"]["rows"][0] == world()["rates"]["C-USA"]["rows"][0]


@pytest.mark.parametrize(("date", "valid"), [("2028-02-29", True), ("2000-02-29", True), ("2027-02-29", False), ("2100-02-29", False), ("2027-04-31", False)])
def test_leap_days(date: str, valid: bool) -> None:
    from plugin.world import day_number

    if valid:
        day_number(date)
    else:
        with pytest.raises(ValueError, match="calendar date"):
            day_number(date)


def test_consecutive_days_roll_over_a_month_and_a_year() -> None:
    from plugin.world import day_number

    assert day_number("2027-01-01") - day_number("2026-12-31") == 1
    assert day_number("2028-03-01") - day_number("2028-02-29") == 1
    assert day_number("2027-03-01") - day_number("2027-02-28") == 1


def test_the_generator_reproduces_the_committed_fixtures() -> None:
    written = files()
    assert sorted(written) == sorted(
        str(path.relative_to(DATA)) for path in DATA.rglob("*.json")
    )
    for path, text in written.items():
        assert (DATA / path).read_text(encoding="utf-8") == text, path


@pytest.mark.parametrize("location_id", sorted(SOURCE_ROWS))
def test_the_rates_are_the_sources_printed_amounts(location_id: str) -> None:
    currency, breakfast, lunch, dinner, total, commercial, private = SOURCE_ROWS[location_id]
    location = world()["rates"][location_id]
    assert location["currency"] == currency and location["effective_date"] == "2026-10-01"
    for row, incidental in zip(location["rows"], (commercial, private), strict=True):
        assert (row["breakfast_minor"], row["lunch_minor"], row["dinner_minor"], row["meal_total_minor"]) == (breakfast, lunch, dinner, total)
        assert row["incidental_minor"] == incidental


def utc_of(local, code):
    tz = json.loads((DATA / "airports.json").read_text(encoding="utf-8"))[code]["tz"]
    moment = datetime.strptime(local, "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(tz))
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_utc_times_and_minutes_agree_with_the_local_times(scenario: str) -> None:
    facts = load_scenario(scenario)
    for segment in facts["outbound"]:
        assert utc_of(segment["depart_local"], segment["origin"]) == segment["depart_utc"]
        assert utc_of(segment["arrive_local"], segment["destination"]) == segment["arrive_utc"]
    assert facts["traveller_id"] in world()["travellers"]
    assert facts["destination"]["rate_location_id"] in world()["rates"]


def mutated(tmp_path: Path, change):
    """A copy of the data folder with one change applied to the paris-assembly scenario."""
    (tmp_path / "scenarios").mkdir()
    for name in ("rates.json", "travellers.json"):
        (tmp_path / name).write_text((DATA / name).read_text(encoding="utf-8"), encoding="utf-8")
    facts = copy.deepcopy(load_scenario("paris-assembly"))
    change(facts)
    (tmp_path / "scenarios" / "paris-assembly.json").write_text(json.dumps(facts), encoding="utf-8")
    return tmp_path


def set_path(*keys_and_value):
    *keys, value = keys_and_value

    def change(facts):
        target = facts
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value

    return change


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (set_path("outbound", 0, "in_air_minutes", 76), "in_air_minutes"),
        (set_path("outbound", 0, "connection_after", "minutes", 59), "connection minutes"),
        (set_path("outbound", 0, "connection_after", None), "connection is malformed"),
        (set_path("outbound", 1, "connection_after", {"minutes": 0, "overnight_stop": False}), "last segment"),
        (set_path("outbound", 1, "origin", "YYZ"), "does not leave"),
        (set_path("outbound", 1, "cabins_sold", ["business"]), "economy"),
        (set_path("outbound", 1, "cabins_sold", ["business", "economy"]), "lowest first"),
        (set_path("outbound", 1, "segment_id", "S1"), "unique"),
        (set_path("outbound", 0, "depart_utc", "2026-12-06 22:45"), "YYYY-MM-DDTHH:MMZ"),
        (set_path("status_days", 1, "date", "2026-12-09"), "consecutive"),
        (set_path("status_days", 0, "status_start_local", "24:00"), "HH:MM"),
        (set_path("status_days", 3, "status_start_local", "18:00"), "ends before it starts"),
        (set_path("status_days", 0, "status_start_local", None), "only the first status day has a status_start_local"),
        (set_path("status_days", 1, "status_start_local", "09:00"), "only the first status day has a status_start_local"),
        (set_path("status_days", 3, "status_end_local", None), "only the last status day has a status_end_local"),
        (set_path("status_days", 1, "status_end_local", "22:00"), "only the last status day has a status_end_local"),
        (set_path("status_days", 0, "meals_provided", ["dinner", "dinner"]), "distinct"),
        (set_path("status_days", 0, "date", "2026-02-30"), "calendar date"),
        (set_path("status_days", [{"date": f"2027-01-{day:02d}", "status_start_local": None, "status_end_local": None, "meals_provided": []} for day in range(1, 32)]), "1 to 30"),
        (set_path("accommodation", "hotel"), "accommodation"),
        (set_path("scenario", "london-secondment"), "names another scenario"),
        (set_path("outbound", []), "at least one"),
    ],
)
def test_the_loader_refuses_inconsistent_fixtures(tmp_path: Path, change, match: str) -> None:
    folder = mutated(tmp_path, change)
    with pytest.raises(ValueError, match=match):
        load_scenario_from(folder, "paris-assembly")


def test_the_loader_refuses_unsafe_ids_and_unreadable_files(tmp_path: Path) -> None:
    for bad in ("../rates", "Paris", "", None, 7):
        with pytest.raises(ValueError):
            load_scenario_from(DATA, bad)
    (tmp_path / "rates.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "travellers.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read rates.json"):
        load_world(tmp_path)


def test_a_rate_row_whose_total_is_not_its_meals_is_refused(tmp_path: Path) -> None:
    rates = json.loads((DATA / "rates.json").read_text(encoding="utf-8"))
    rates["D-FR-PARIS"]["rows"][0]["meal_total_minor"] += 1
    (tmp_path / "rates.json").write_text(json.dumps(rates), encoding="utf-8")
    (tmp_path / "travellers.json").write_text((DATA / "travellers.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="meal total"):
        load_world(tmp_path)


def test_the_product_page_lists_every_scenario_and_the_readme_every_tool() -> None:
    product = (ROOT / "product" / "product.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    tools_section = readme.split("## Tools")[1].split("## Layout")[0]
    for scenario in SCENARIOS:
        assert scenario in product and f"`{scenario}`" in readme
    for name in ("get_trip_request", "get_allowance_rates", "compute_njc_entitlement", "njc-trip-entitlement"):
        assert f"`{name}`" in tools_section
