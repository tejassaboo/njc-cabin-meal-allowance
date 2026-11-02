"""What the tests share: paths, the scenarios, the hand-written cases, and values built the way
NanoAgent's sandbox builds them (build_output from plain JSON)."""

import json
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import NjcEntitlementOutput, NjcScenario, ScenarioInput
from plugin import compute_njc_entitlement

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "plugin" / "data"
TASK = "njc-trip-entitlement"
SCENARIOS = [member.value for member in NjcScenario]


def case(scenario):
    """The hand-written case: {scenario, note, expected, broken: [{why, change, reason}]}."""
    return json.loads((ROOT / "tests" / "cases" / f"{scenario}.json").read_text(encoding="utf-8"))


def arguments(scenario):
    return build_output({"scenario": scenario}, ScenarioInput)


def reference(scenario):
    """The pinned reference, as NanoAgent pins it: the reference tool's output, built into its class."""
    return build_output(plain_output(compute_njc_entitlement(arguments(scenario))), NjcEntitlementOutput)


def verdict(scenario, output, *, pinned=True):
    """verify_task on a plain-JSON submission, with the reference pinned as in a real run."""
    return verifier.verify_task(
        TASK, arguments(scenario), build_output(output, NjcEntitlementOutput), reference(scenario) if pinned else None, "."
    )
