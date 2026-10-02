"""Ai_cheshm plugin entry point for Audio Intelligence.

The implementation deliberately keeps platform imports at the integration boundary.
Heavy media work belongs to Ai_Media_Intelligence_Core providers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .manifest import AGENT_MANIFEST

try:
    from core.base_agent import BaseAgent, Manifest
    from core.events import AgentEvent
    from core.platform.contracts import ExecutionContext
    from core.session import Session
except ImportError:  # Allows repository-level contract tests before host integration.
    BaseAgent = object  # type: ignore[assignment,misc]
    Manifest = None  # type: ignore[assignment,misc]
    AgentEvent = Any  # type: ignore[assignment,misc]
    ExecutionContext = Any  # type: ignore[assignment,misc]
    Session = Any  # type: ignore[assignment,misc]


class AudioIntelligenceAgent(BaseAgent):
    """User-facing Audio Intelligence plugin."""

    if Manifest is not None:
        manifest = Manifest(**AGENT_MANIFEST)
    else:
        manifest = AGENT_MANIFEST

    async def run_with_context(
        self,
        message: str,
        params: dict[str, Any],
        session: Session,
        context: ExecutionContext,
    ) -> AsyncIterator[AgentEvent]:
        """Validate the plugin boundary before Core orchestration is connected."""
        if context.is_cancelled():
            if AgentEvent is Any:
                return
            yield AgentEvent(type="cancelled", data={"execution_id": context.execution_id})
            return

        if not str(message or "").strip():
            yield AgentEvent(
                type="error",
                data={
                    "text": "Please provide an audio request.",
                    "execution_id": context.execution_id,
                },
            )
            return

        yield AgentEvent(
            type="progress",
            data={
                "stage": "validated",
                "message": "Audio request accepted; Core capability orchestration is next.",
                "execution_id": context.execution_id,
            },
        )
        yield AgentEvent(
            type="done",
            data={
                "execution_id": context.execution_id,
                "status": "foundation_ready",
            },
        )

    async def run(self, message: str, params: dict, session: Session) -> AsyncIterator[AgentEvent]:
        """Platform compatibility entry point.

        Ai_cheshm normally invokes execute()/run_with_context().
        """
        raise RuntimeError("AudioIntelligenceAgent requires Ai_cheshm AgentRuntime context")


__all__ = ["AudioIntelligenceAgent"]
