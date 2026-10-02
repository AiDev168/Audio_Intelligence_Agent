from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from agent.core_adapter import CoreCapabilityGateway
from agent.service import AudioIntelligenceService


@dataclass
class FakeFileAccess:
    path: str = "C:/trusted/audio.wav"

    def resolve(self, url: str) -> str:
        assert url == "/storage/audio.wav"
        return self.path


@dataclass
class FakeSession:
    files: list[dict] = field(
        default_factory=lambda: [
            {"url": "/storage/audio.wav", "name": "audio.wav", "active": True, "legacy": False}
        ]
    )
    state: dict = field(default_factory=dict)

    def get_active_files(self):
        return [dict(item) for item in self.files if item.get("active", True)]


@dataclass
class FakeContext:
    execution_id: str = "exec-1"
    metadata: dict = field(default_factory=dict)


class FakeCoreFacade:
    async def execute(self, capability, media, *, options, host_context):
        return {
            "capability": capability,
            "media": media,
            "options": options,
            "execution_id": host_context.execution_id,
        }


@dataclass(frozen=True)
class FakeEvidenceQuery:
    query: str
    limit: int = 20


class FakeCoreModule:
    AudioEvidenceQuery = FakeEvidenceQuery


def test_input_falls_back_to_active_session_file():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )
    url = service._resolve_input_url({}, FakeSession())
    assert url == "/storage/audio.wav"


def test_rejects_arbitrary_local_paths():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )
    with pytest.raises(ValueError, match="storage URLs"):
        service._validate_storage_url("C:/audio.wav")


def test_operation_aliases_are_stable():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )
    assert service._resolve_operation("", {"operation": "transcription"}) == "transcribe"
    assert service._resolve_operation("", {"operation": "qa"}) == "ask"


def test_evidence_limit_defaults_to_agent_setting():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={"evidence_limit": 7},
    )
    service.settings["evidence_limit"] = 7
    class Core:
        AudioEvidenceQuery = FakeEvidenceQuery

    query = service._make_evidence_query(
        type("Gateway", (), {"core": Core})(),
        "find the key point",
        {},
    )
    assert query.query == "find the key point"
    assert query.limit == 7


def test_core_gateway_forwards_host_context_without_exposing_provider_objects():
    context = FakeContext()
    gateway = CoreCapabilityGateway(FakeCoreFacade(), context)

    async def run():
        return await gateway.execute(
            "transcription",
            {"asset_id": "asset-1"},
            options={"request_id": "req-1"},
        )

    result = asyncio.run(run())
    assert result["capability"] == "transcription"
    assert result["execution_id"] == "exec-1"
    assert result["options"] == {"request_id": "req-1"}
