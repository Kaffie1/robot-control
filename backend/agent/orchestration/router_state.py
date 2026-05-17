from typing import Any, TypedDict


class FaultRouteState(TypedDict, total=False):
    user_message: str
    playbooks: list[dict[str, str]]
    selected_playbook_id: str
    selected_playbook_title: str
    reason: str
    resume_continuation: dict[str, Any] | None
    prefetched_playbook_id: str
    prefetched_playbook_title: str
    prefetched_reason: str


class FaultChatState(TypedDict, total=False):
    user_message: str
    conversation_history: list[dict[str, str]]
    playbooks: list[dict[str, str]]
    selected_playbook_id: str
    selected_playbook_title: str
    reason: str
    prefetched_playbook_id: str
    prefetched_playbook_title: str
    prefetched_reason: str
    runtime_context: dict[str, Any]
    tool_context: dict[str, Any]
    effective_tool_context: dict[str, Any]
    resume_continuation: dict[str, Any] | None
    confirmation_response: str
    messages: list[Any]
    tool_traces: list[dict[str, Any]]
    scripted_playbook: dict[str, Any] | None
    pending_confirmation: dict[str, Any] | None
    pending_playbook_render: dict[str, Any] | None
    playbook_render_ready: bool
    playbook_resume_state: dict[str, Any] | None
    model_loop_count: int
    response: Any
    response_content: str
    parsed_response: dict[str, Any] | None
    pending_commands: list[dict[str, Any]]
    final_message: str
    result_kind: str
