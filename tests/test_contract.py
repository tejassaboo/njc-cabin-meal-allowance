"""Structured input and structured output: every contract field is typed and described, every policy fact
reaches the agent in a typed field (never only in prose), and nothing the verifier grades is free text."""

import dataclasses
import typing
from enum import Enum

import contract
from contract import (
    Accommodation,
    Connection,
    Currency,
    Destination,
    Meal,
    NjcCabin,
    NjcEntitlementOutput,
    RateRow,
    RatesOutput,
    Segment,
    StatusDay,
    TripRequestOutput,
)

CONTRACT_CLASSES = [
    value
    for value in vars(contract).values()
    if isinstance(value, type) and dataclasses.is_dataclass(value) and value.__module__ == contract.__name__
]


def annotated_fields(cls):
    """(name, type, description) for every field, from the class's Annotated hints."""
    hints = typing.get_type_hints(cls, include_extras=True)
    for field in dataclasses.fields(cls):
        hint = hints[field.name]
        assert typing.get_origin(hint) is typing.Annotated, f"{cls.__name__}.{field.name} is not Annotated"
        base, *metadata = typing.get_args(hint)
        yield field.name, base, metadata[0]


def types_of(cls):
    return {name: base for name, base, _ in annotated_fields(cls)}


def test_every_field_is_annotated_with_a_description() -> None:
    assert len(CONTRACT_CLASSES) >= 12
    for cls in CONTRACT_CLASSES:
        for name, _, description in annotated_fields(cls):
            assert isinstance(description, str) and len(description.split()) >= 3, f"{cls.__name__}.{name}"


def test_every_policy_fact_reaches_the_agent_in_a_typed_field() -> None:
    trip = types_of(TripRequestOutput)
    assert trip["accommodation"] is Accommodation
    assert trip["outbound"] == list[Segment] and trip["status_days"] == list[StatusDay]
    assert types_of(Destination)["in_canada_or_continental_usa"] is bool
    assert types_of(Destination)["rate_location_id"] is str
    segment = types_of(Segment)
    assert segment["in_air_minutes"] is int and segment["cabins_sold"] == list[NjcCabin]
    assert segment["connection_after"] == (Connection | None)
    assert types_of(Connection) == {"minutes": int, "overnight_stop": bool}
    day = types_of(StatusDay)
    assert day["status_start_local"] == (str | None) and day["status_end_local"] == (str | None)
    assert day["meals_provided"] == list[Meal]
    assert types_of(RatesOutput)["currency"] is Currency
    row = types_of(RateRow)
    assert all(row[name] is int for name in row if name.endswith("_minor"))


def test_the_graded_output_has_no_free_text() -> None:
    for name, base, _ in annotated_fields(NjcEntitlementOutput):
        if name == "segment_cabins":
            assert base == list[contract.SegmentCabin]
            assert types_of(contract.SegmentCabin) == {"segment_id": str, "cabin": NjcCabin}  # an id checked against the journey
            continue
        assert base is int or (isinstance(base, type) and issubclass(base, Enum)), f"{name}: {base}"


def test_formats_units_and_nulls_are_stated() -> None:
    for cls in CONTRACT_CLASSES:
        for name, base, description in annotated_fields(cls):
            if name.endswith(("_utc", "depart_local", "arrive_local", "_date")) or name == "date":
                assert "YYYY-MM-DD" in description, f"{cls.__name__}.{name}"
            if name.startswith("status_") and name.endswith("_local"):
                assert "HH:MM" in description, f"{cls.__name__}.{name}"
            if name.endswith("_minor"):
                assert "hundredths" in description, f"{cls.__name__}.{name}"
            if name.endswith("minutes"):
                assert "minutes" in description.lower(), f"{cls.__name__}.{name}"
            if typing.get_origin(base) is not None and type(None) in typing.get_args(base):
                assert "null" in description, f"{cls.__name__}.{name} does not say what null means"
            if typing.get_origin(base) is list:
                assert any(word in description for word in ("order", "first", "earliest")), f"{cls.__name__}.{name} states no ordering"


def test_every_choice_is_an_enum_with_string_values() -> None:
    for enum in (NjcCabin, Meal, Accommodation, Currency, contract.Appendix, contract.NjcScenario):
        assert all(isinstance(member.value, str) for member in enum)
    assert [member.value for member in NjcCabin] == ["economy", "premium_economy", "business"]
