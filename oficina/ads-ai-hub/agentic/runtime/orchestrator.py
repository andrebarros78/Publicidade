from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agents import Runner
from agents.stream_events import AgentUpdatedStreamEvent

from agentic.runtime.autonomous_team import RuntimeTeam, build_team

PublishFn = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class MissionRequest:
    mission_id: str
    objective: str
    task_type: str = "ads_operation"
    priority: str = "normal"
    max_turns: int = 20


class MissionConfigurationError(RuntimeError):
    pass


def configured_model() -> str:
    model = os.getenv("ADS_AGENT_MODEL", "").strip()
    if not model:
        raise MissionConfigurationError("ADS_AGENT_MODEL is not configured")
    return model


def agent_id_by_name(team: RuntimeTeam) -> dict[str, str]:
    return {agent.name: agent_id for agent_id, agent in team.agents.items()}


async def execute_mission(
    request: MissionRequest,
    publish: PublishFn,
    *,
    team: RuntimeTeam | None = None,
    runner_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Run a production mission through the Agents SDK and mirror agent changes to the Task Bus.

    The orchestrator never fabricates specialists. Only agents actually selected by the SDK are
    marked active. Every touched agent is returned to REST when the mission finishes or fails.
    """
    runtime_team = team or build_team(model=configured_model())
    run_streamed = runner_factory or Runner.run_streamed
    name_to_id = agent_id_by_name(runtime_team)
    chief_id = "chief_ads_officer"
    touched: list[str] = []
    current_id: str | None = None

    async def set_state(agent_id: str, state: str, progress: float = 0, **extra: Any) -> None:
        if agent_id not in touched:
            touched.append(agent_id)
        await publish({
            "agent_id": agent_id,
            "operational_state": state,
            "task_id": request.mission_id,
            "task_type": request.task_type,
            "progress": progress,
            "priority": request.priority,
            "source": "production",
            **extra,
        })

    try:
        current_id = chief_id
        await set_state(chief_id, "working", 1)
        result = run_streamed(runtime_team.chief, request.objective, max_turns=request.max_turns)

        async for event in result.stream_events():
            if not isinstance(event, AgentUpdatedStreamEvent):
                continue
            next_id = name_to_id.get(event.new_agent.name)
            if not next_id or next_id == current_id:
                continue
            if current_id:
                await set_state(current_id, "waiting", 50)
            current_id = next_id
            await set_state(next_id, "working", 50)

        if current_id:
            await set_state(current_id, "working", 100)

        final_output = result.final_output
        last_agent_id = name_to_id.get(getattr(result.last_agent, "name", ""), current_id or chief_id)
        return {
            "mission_id": request.mission_id,
            "status": "completed",
            "last_agent_id": last_agent_id,
            "agents_touched": touched.copy(),
            "final_output": final_output,
        }
    except Exception:
        if current_id:
            await set_state(current_id, "attention", 0)
        raise
    finally:
        for agent_id in reversed(touched):
            await publish({
                "agent_id": agent_id,
                "operational_state": "rest",
                "task_id": None,
                "task_type": None,
                "progress": 0,
                "priority": "normal",
                "source": "production",
            })
