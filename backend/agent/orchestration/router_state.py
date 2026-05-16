from typing import TypedDict


class FaultRouteState(TypedDict, total=False):
    user_message: str
    playbooks: list[dict[str, str]]
    selected_playbook_id: str
    selected_playbook_title: str
    reason: str
