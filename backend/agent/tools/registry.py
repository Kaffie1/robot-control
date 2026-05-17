from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict

from ...errors import ApiError
from ..common import append_fault_trace, logger
from .runtime import AgentToolDefinition


class EmptyArgs(BaseModel):
    pass


class RobotArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    robot_id: str | None = None


class ApprovalArgs(RobotArgs):
    operator_approved: bool | None = None


class RelocalizationArgs(RobotArgs):
    map_name: str | None = None
    force: bool | None = None


class RecoveryZoneArgs(RobotArgs):
    recovery_zone: str | None = None


def _mock_check_localization(payload: RobotArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    context = dict(tool_context or {})
    localized = bool(context.get("operator_approved") and context.get("map_name") and context.get("recovery_zone"))
    return {
        "localized": localized,
        "robot_id": payload.robot_id,
        "source": "mock",
    }


def _mock_record_operator_approval(payload: ApprovalArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "accepted": bool(payload.operator_approved),
        "robot_id": payload.robot_id,
        "source": "mock",
    }


def _mock_trigger_relocalization(payload: RelocalizationArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "accepted": bool(payload.map_name),
        "robot_id": payload.robot_id,
        "map_name": payload.map_name,
        "force": bool(payload.force),
        "source": "mock",
    }


def _mock_set_recovery_zone(payload: RecoveryZoneArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "accepted": bool(payload.recovery_zone),
        "robot_id": payload.robot_id,
        "zone": payload.recovery_zone,
        "expected_zone": payload.recovery_zone,
        "source": "mock",
    }


def _mock_check_localization_detail(payload: RobotArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    import time

    return {
        "robot_id": payload.robot_id,
        "pose_timestamp": time.time(),
        "message": "pose timestamp ok",
        "source": "mock",
    }


def _mock_check_localization_quality(payload: RobotArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "robot_id": payload.robot_id,
        "score": 88,
        "message": "quality ok",
        "source": "mock",
    }


def _mock_diagnose_robot_status(payload: RobotArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    context = dict(tool_context or {})
    return {
        "robot_id": payload.robot_id,
        "localized": bool(context.get("operator_approved") and context.get("map_name") and context.get("recovery_zone")),
        "map_name": context.get("map_name"),
        "recovery_zone": context.get("recovery_zone"),
        "status": "needs_recovery" if not context.get("recovery_zone") else "ready",
        "summary": "mock diagnose result",
        "source": "mock",
    }


MOCK_TOOL_DEFINITIONS = [
    AgentToolDefinition(
        name="check_localization",
        description="Mock localization state checker.",
        args_schema=RobotArgs,
        handler=_mock_check_localization,
    ),
    AgentToolDefinition(
        name="record_operator_approval",
        description="Mock operator approval recorder.",
        args_schema=ApprovalArgs,
        handler=_mock_record_operator_approval,
    ),
    AgentToolDefinition(
        name="trigger_relocalization",
        description="Mock relocalization trigger.",
        args_schema=RelocalizationArgs,
        handler=_mock_trigger_relocalization,
    ),
    AgentToolDefinition(
        name="set_recovery_zone",
        description="Mock recovery zone setter.",
        args_schema=RecoveryZoneArgs,
        handler=_mock_set_recovery_zone,
    ),
    AgentToolDefinition(
        name="check_localization_detail",
        description="Mock localization detail checker.",
        args_schema=RobotArgs,
        handler=_mock_check_localization_detail,
    ),
    AgentToolDefinition(
        name="check_localization_quality",
        description="Mock localization quality checker.",
        args_schema=RobotArgs,
        handler=_mock_check_localization_quality,
    ),
    AgentToolDefinition(
        name="diagnose_robot_status",
        description="Mock robot status diagnostic tool.",
        args_schema=RobotArgs,
        handler=_mock_diagnose_robot_status,
    ),
]


class AgentToolRegistry:
    def __init__(self) -> None:
        self._definitions: list[AgentToolDefinition] = list(MOCK_TOOL_DEFINITIONS)
        self._by_name = {item.name: item for item in self._definitions}

    def count(self) -> int:
        return len(self._definitions)

    def list_tool_names(self) -> list[str]:
        return [item.name for item in self._definitions]

    def call_tool(self, name: str, arguments: dict[str, Any] | None, tool_context: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = self._by_name.get(str(name or "").strip())
        if definition is None:
            raise ApiError(f"未找到 agent 工具: {name}")
        payload = definition.args_schema.model_validate(arguments or {})
        logger.info("Agent 工具调用 | tool=%s", definition.name)
        append_fault_trace(
            "agent_tool_registry_call_start",
            {
                "tool_name": definition.name,
                "arguments": arguments or {},
            },
        )
        result = definition.handler(payload, tool_context)
        append_fault_trace(
            "agent_tool_registry_call_end",
            {
                "tool_name": definition.name,
                "arguments": arguments or {},
                "result": result,
            },
        )
        return result

agent_tool_registry = AgentToolRegistry()
