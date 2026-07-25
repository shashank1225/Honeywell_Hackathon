"""Single deterministic gateway for every actuator-adjacent setpoint change."""

from __future__ import annotations

import weakref

from app.schemas.telemetry import OperatingPolicy, SafetyValidationResult, Setpoints
from app.services.safety_sentinel import SafetySentinel, safety_sentinel
from app.simulation.state import BuildingState, building_state

_state_sentinels: weakref.WeakKeyDictionary[BuildingState, SafetySentinel] = weakref.WeakKeyDictionary()


def _sentinel_for(state: BuildingState, configured: SafetySentinel) -> SafetySentinel:
    if configured is not safety_sentinel:
        return configured
    if state is building_state:
        return safety_sentinel
    sentinel = _state_sentinels.get(state)
    if sentinel is None:
        sentinel = SafetySentinel()
        _state_sentinels[state] = sentinel
    return sentinel


def apply_safe_setpoints(
    state: BuildingState,
    proposed: Setpoints,
    *,
    sentinel: SafetySentinel = safety_sentinel,
    emergency: bool = False,
    policy: OperatingPolicy | None = None,
) -> SafetyValidationResult:
    """Validate and apply a control proposal; no caller may bypass this gateway."""
    _ = policy  # retained as explicit audit context for the control contract
    current = state.get_setpoints()
    result = _sentinel_for(state, sentinel).validate(current, proposed, emergency=emergency)
    if result.accepted and result.safe_setpoints is not None:
        state.update_setpoints(**result.safe_setpoints.model_dump())
    return result
