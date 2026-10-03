from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from audio_intelligence_agent.agent import _CAPABILITY_LABELS, _error_hint
from audio_intelligence_agent.core_adapter import CoreCapabilityError, CoreCapabilityGateway


def test_core_capability_error_keeps_structured_safe_diagnostics() -> None:
    cause = ValueError("request failed api_key=super-secret")
    error = CoreCapabilityError(
        "Media Core capability 'summarization' could not be executed.",
        capability="summarization",
        cause=cause,
    )

    assert error.capability == "summarization"
    assert error.cause_type == "ValueError"
    assert "super-secret" not in error.detail
    assert "[REDACTED]" in error.detail


def test_service_execution_failure_is_wrapped_as_core_capability_error() -> None:
    class FailingService:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("provider unavailable")

    context = SimpleNamespace(execution_id="exec-1", metadata={}, is_cancelled=lambda: False)
    gateway = CoreCapabilityGateway(FailingService(), context)

    async def run():
        with pytest.raises(CoreCapabilityError) as raised:
            await gateway.execute("summarization", object())

        assert raised.value.capability == "summarization"
        assert raised.value.cause_type == "RuntimeError"
        assert "provider unavailable" in raised.value.detail

    asyncio.run(run())


def test_audio_error_hints_cover_user_relevant_capabilities() -> None:
    assert _CAPABILITY_LABELS["transcription"] == "تبدیل گفتار به متن"
    assert "faster-whisper" in _error_hint("transcription").lower()
    assert "api" in _error_hint("summarization").lower()
    assert "hugging face" in _error_hint("diarization").lower()



def test_core_gateway_prefers_host_owned_core_instance() -> None:
    core_marker = object()
    service = SimpleNamespace(
        core=core_marker,
        execute=lambda *args, **kwargs: None,
    )
    context = SimpleNamespace(execution_id="exec-host", metadata={})

    gateway = CoreCapabilityGateway(service, context)

    assert gateway.core is core_marker
