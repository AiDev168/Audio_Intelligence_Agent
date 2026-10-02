"""Ai_cheshm plugin entry point for Audio Intelligence."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from .core_adapter import CoreCapabilityError
from .manifest import AGENT_MANIFEST
from .service import AudioIntelligenceService

try:
    from core.base_agent import BaseAgent, Manifest
    from core.events import AgentEvent
    from core.platform.contracts import ExecutionContext
    from core.session import Session
except ImportError:
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
        if context.is_cancelled():
            yield AgentEvent(type="cancelled", data={"execution_id": context.execution_id})
            return

        if not str(message or "").strip() and not any(
            str(params.get(key) or "").strip() for key in ("operation", "query", "audio_file")
        ):
            yield AgentEvent(
                type="error",
                data={
                    "text": "Please provide an audio request.",
                    "execution_id": context.execution_id,
                },
            )
            return

        file_access = context.capabilities.get("agent_file_access")
        artifact_store = context.capabilities.get("artifact_store")
        media_core = context.capabilities.get("media_intelligence_core")
        missing = [
            name
            for name, value in (
                ("agent_file_access", file_access),
                ("artifact_store", artifact_store),
                ("media_intelligence_core", media_core),
            )
            if value is None
        ]
        if missing:
            yield AgentEvent(
                type="error",
                data={
                    "text": "Audio Intelligence is not fully configured on the platform.",
                    "execution_id": context.execution_id,
                    "missing_capability_count": len(missing),
                },
            )
            return

        yield AgentEvent(
            type="thinking",
            data={
                "text": "Preparing the audio analysis...",
                "execution_id": context.execution_id,
            },
        )

        try:
            service = AudioIntelligenceService(
                core_service=media_core,
                file_access=file_access,
                settings=self.settings,
            )
            result = await service.execute(
                message=str(message or ""),
                params=dict(params or {}),
                session=session,
                context=context,
            )
        except (ValueError, FileNotFoundError, PermissionError) as exc:
            yield AgentEvent(
                type="error",
                data={
                    "text": str(exc),
                    "execution_id": context.execution_id,
                },
            )
            return
        except CoreCapabilityError:
            yield AgentEvent(
                type="error",
                data={
                    "text": (\n                        "The configured audio analysis service could not complete this operation."\n                    ),
                    "execution_id": context.execution_id,
                },
            )
            return

        if context.is_cancelled():
            yield AgentEvent(
                type="cancelled",
                data={
                    "text": "Audio analysis was cancelled.",
                    "execution_id": context.execution_id,
                },
            )
            return

        report_url = self._save_report(result, artifact_store, context)
        if report_url:
            yield AgentEvent(
                type="artifact",
                data={
                    "type": "file",
                    "title": f"audio_intelligence_{context.execution_id}.json",
                    "url": report_url,
                    "agent_id": context.agent_id,
                    "meta": {
                        "operation": result.get("operation"),
                        "asset_id": result.get("asset_id"),
                        "format": "json",
                    },
                },
            )

        answer = result.get("answer")
        if isinstance(answer, dict):
            citations = answer.get("citations") or []
            if citations:
                yield AgentEvent(
                    type="sources",
                    data={
                        "execution_id": context.execution_id,
                        "sources": [
                            {
                                "evidence_id": item.get("evidence_id"),
                                "asset_id": item.get("asset_id"),
                                "start": (item.get("interval") or {}).get("start"),
                                "end": (item.get("interval") or {}).get("end"),
                                "text": item.get("excerpt"),
                            }
                            for item in citations
                            if isinstance(item, dict)
                        ],
                    },
                )

        done_data = {
            "execution_id": context.execution_id,
            "status": "completed",
            "operation": result.get("operation"),
            "asset_id": result.get("asset_id"),
        }
        if isinstance(answer, dict) and answer.get("answer"):
            done_data["text"] = str(answer["answer"])
        elif result.get("transcript_text"):
            done_data["text"] = "Audio transcription completed."
        elif result.get("summary"):
            done_data["text"] = "Audio analysis completed."
        else:
            done_data["text"] = "Audio analysis completed."

        yield AgentEvent(type="progress", data={
            "stage": "completed",
            "percent": 100,
            "text": "Audio analysis completed.",
            "execution_id": context.execution_id,
        })
        yield AgentEvent(type="done", data=done_data)

    @staticmethod
    def _save_report(result: dict[str, Any], artifact_store: Any, context: ExecutionContext) -> str:
        try:
            content = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            return str(
                artifact_store.save(
                    f"audio_intelligence_{context.execution_id}.json",
                    content,
                )
            )
        except Exception:
            return ""

    async def run(self, message: str, params: dict, session: Session) -> AsyncIterator[AgentEvent]:
        raise RuntimeError("AudioIntelligenceAgent requires Ai_cheshm AgentRuntime context")


__all__ = ["AudioIntelligenceAgent"]
