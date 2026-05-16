from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

from ...models import ApiError
from ..common import append_fault_trace, logger
from .runtime import (
    AgentToolDefinition,
    DockerComposeModuleArgs,
    PingHostArgs,
    RosNameArgs,
    RosServiceCallArgs,
    RosTypeNameArgs,
    handle_docker_compose_down_module,
    handle_docker_compose_up_module,
    handle_ping_host,
    handle_ros_list_services,
    handle_ros_list_topics,
    handle_ros_message_definition,
    handle_ros_service_call,
    handle_ros_service_definition,
    handle_ros_service_info,
    handle_ros_service_type,
    handle_ros_topic_echo,
    handle_ros_topic_info,
    handle_ros_topic_type,
)


class EmptyArgs(BaseModel):
    pass


class AgentToolRegistry:
    def __init__(self) -> None:
        self._definitions = [
            AgentToolDefinition(
                name="ros_list_topics",
                description="列出当前 ROS 环境中的所有 topic。",
                args_schema=EmptyArgs,
                handler=handle_ros_list_topics,
            ),
            AgentToolDefinition(
                name="ros_list_services",
                description="列出当前 ROS 环境中的所有 service。",
                args_schema=EmptyArgs,
                handler=handle_ros_list_services,
            ),
            AgentToolDefinition(
                name="ros_topic_info",
                description="查看指定 topic 的连接信息、发布者和订阅者。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_info,
            ),
            AgentToolDefinition(
                name="ros_topic_type",
                description="查看指定 topic 的消息类型。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_type,
            ),
            AgentToolDefinition(
                name="ros_message_definition",
                description="查看 ROS 消息类型定义，并尽量展开嵌套字段。",
                args_schema=RosTypeNameArgs,
                handler=handle_ros_message_definition,
            ),
            AgentToolDefinition(
                name="ros_topic_echo",
                description="抓取一次 topic 样本消息，用于现场排查。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_echo,
            ),
            AgentToolDefinition(
                name="ros_service_info",
                description="查看指定 service 的连接和节点信息。",
                args_schema=RosNameArgs,
                handler=handle_ros_service_info,
            ),
            AgentToolDefinition(
                name="ros_service_type",
                description="查看指定 service 的服务类型。",
                args_schema=RosNameArgs,
                handler=handle_ros_service_type,
            ),
            AgentToolDefinition(
                name="ros_service_definition",
                description="查看 ROS 服务类型定义，并尽量展开嵌套字段。",
                args_schema=RosTypeNameArgs,
                handler=handle_ros_service_definition,
            ),
            AgentToolDefinition(
                name="ros_service_call",
                description="调用指定 ROS service，并返回执行结果。",
                args_schema=RosServiceCallArgs,
                handler=handle_ros_service_call,
            ),
            AgentToolDefinition(
                name="ping_host",
                description="从当前机器人侧 ping 指定主机，用于确认网络通信是否正常。",
                args_schema=PingHostArgs,
                handler=handle_ping_host,
            ),
            AgentToolDefinition(
                name="docker_compose_down_module",
                description="停止单个 docker compose 模块服务。",
                args_schema=DockerComposeModuleArgs,
                handler=handle_docker_compose_down_module,
            ),
            AgentToolDefinition(
                name="docker_compose_up_module",
                description="启动单个 docker compose 模块服务，并默认等待一段时间让容器稳定。",
                args_schema=DockerComposeModuleArgs,
                handler=handle_docker_compose_up_module,
            ),
        ]
        self._by_name = {item.name: item for item in self._definitions}

    def list_definitions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for definition in self._definitions:
            items.append(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "input_schema": definition.args_schema.model_json_schema(),
                }
            )
        return items

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

    def build_langchain_tools(self, tool_context: dict[str, Any] | None = None) -> list[Any]:
        from langchain_core.tools import StructuredTool

        tools = []
        for definition in self._definitions:
            def make_tool_handler(current_name: str) -> Callable[..., str]:
                def tool_handler(**kwargs: Any) -> str:
                    result = self.call_tool(current_name, kwargs, tool_context)
                    return json.dumps(result, ensure_ascii=False)

                return tool_handler

            tools.append(
                StructuredTool.from_function(
                    func=make_tool_handler(definition.name),
                    name=definition.name,
                    description=definition.description,
                    args_schema=definition.args_schema,
                )
            )
        return tools


agent_tool_registry = AgentToolRegistry()
