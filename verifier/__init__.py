"""The deterministic verifier: each tool's checks live in its own module, on contract instances.

None of the three entry points ever raises: an unknown task or tool id, or any value a check did not
expect, becomes a failed ``verifier-error`` verdict, because a verifier that raises leaves the run with no
verdict at all.
"""

from contract import Task, Tool

from . import entitlement, rates, trip_request
from .checks import result

TOOLS = {Tool.GET_TRIP_REQUEST: trip_request, Tool.GET_ALLOWANCE_RATES: rates, Tool.COMPUTE_NJC_ENTITLEMENT: entitlement}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.NJC_TRIP_ENTITLEMENT: entitlement.verify_task}


def verify_input(tool, value):
    try:
        return TOOLS[Tool(tool)].verify_input(value)
    except Exception as error:  # noqa: BLE001 - the verifier must never raise
        return result(False, f"verifier-error: {error!r}")


def verify_output(tool, input_value, output_value, workspace):
    try:
        return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)
    except Exception as error:  # noqa: BLE001
        return result(False, f"verifier-error: {error!r}")


def verify_task(task, arguments, output, reference, workspace):
    try:
        return TASKS[Task(task)](arguments, output, reference, workspace)
    except Exception as error:  # noqa: BLE001
        return result(False, f"verifier-error: {error!r}")
