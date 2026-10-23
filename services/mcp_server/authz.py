"""Ownership checks shared by the API and every MCP tool handler (policy 10).

A manager may read every work order. A technician may read only work orders assigned to them,
and only asset history for assets on those work orders. Every denied call is written to the
audit log by the caller of `authorize`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Caller:
    sub: str                 # Cognito subject
    role: str                # "manager" or "technician", from the Cognito group claim
    technician_id: str | None = None


def authorize(caller: Caller, action: str, owner_technician_id: str | None,
              owned_asset_ids: frozenset = frozenset(), asset_id: str | None = None) -> tuple[bool, str]:
    if caller.role == "manager":
        return True, "manager may read all work orders"
    if caller.role != "technician" or not caller.technician_id:
        return False, "unknown role"
    if action in ("get_work_order", "list_my_jobs"):
        if owner_technician_id == caller.technician_id:
            return True, "assigned to caller"
        return False, "work order is assigned to another technician"
    if action == "get_asset_history":
        if asset_id in owned_asset_ids:
            return True, "asset is on one of the caller's work orders"
        return False, "asset is not on any of the caller's work orders"
    if action == "search_manuals":
        return True, "manuals are readable by every signed-in user"
    return False, f"unknown action {action}"
