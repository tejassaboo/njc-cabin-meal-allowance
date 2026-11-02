"""Scenario ids are visible to the agent (the task input is the id), so an id must not leak the answer:
no graded output value, no boundary number, no informal rule term, and no category that by itself fixes the
answer. A destination city plus a neutral persona or event noun is flavour only. Modelled on T1's test."""

import re

import contract

# The graded output's Enums, and the input categories whose value alone settles part of the answer
# (an overnight stop breaks continuous air travel; the accommodation picks the incidental row; a cabin that is
# not sold moves the segment down a class).
SCENARIO_ENUMS = [contract.NjcScenario]
GRADED_ENUMS = [contract.NjcCabin, contract.Currency, contract.Meal]
CATEGORY_ENUMS = [contract.Accommodation, contract.Appendix]
CATEGORY_TERMS = {"overnight", "daytime", "layover", "stopover", "wait", "connection", "continuous", "nonstop",
                  "module", "provided", "incidental", "incidentals", "meals", "hotel", "sister", "relatives",
                  "sold", "unsold", "no", "not", "without", "domestic", "international", "abroad"}

UNIVERSAL_TERMS = {
    # informal rule terms (never rule terms in a handbook)
    "red", "eye", "redeye", "long", "haul", "longhaul", "short",
    # boundary and threshold words
    "boundary", "threshold", "limit", "cap", "edge", "exact", "exactly", "over", "under", "max", "min",
    "minutes", "hours", "days", "cents", "dollars",
    # decision and verdict words
    "approve", "approved", "deny", "denied", "reject", "rejected", "compliant", "noncompliant", "violation",
    "exception", "upgrade", "downgrade", "valid", "invalid", "pass", "fail", "allowed", "disallowed",
    "cheap", "cheapest", "trap",
    # spelled-out numbers
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "sixteen", "twenty", "hundred",
}


def enum_tokens(enums):
    """Every underscore-separated word of every member value, lower-cased."""
    return {word for enum in enums for member in enum for word in str(member.value).lower().split("_")}


FORBIDDEN = UNIVERSAL_TERMS | enum_tokens(GRADED_ENUMS) | enum_tokens(CATEGORY_ENUMS) | CATEGORY_TERMS
IDS = [member.value for enum in SCENARIO_ENUMS for member in enum]


def test_ids_are_kebab_case_without_numbers():
    for scenario in IDS:
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", scenario), f"{scenario}: lower-case words only, no digits"


def test_ids_leak_no_answer_term():
    for scenario in IDS:
        leaked = sorted(set(scenario.split("-")) & FORBIDDEN)
        assert not leaked, f"{scenario} leaks {leaked}"


def test_ids_are_unique():
    assert len(IDS) == len(set(IDS))


def test_the_old_leaky_ids_would_have_been_caught():
    """The ids renamed in the Tier-2 integration pass each fail the word check."""
    for old in ("tokyo-no-business", "nairobi-overnight-heathrow", "nairobi-daytime-wait"):
        assert set(old.split("-")) & FORBIDDEN, old
