from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from audio_intelligence_agent.core_adapter import CoreCapabilityGateway
from audio_intelligence_agent.service import AudioIntelligenceService


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


def test_input_falls_back_to_active_session_file():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )
    url = service._resolve_input_url({}, FakeSession())
    assert url == "/storage/audio.wav"


def test_selected_audio_document_wins_over_first_active_file():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    class Session:
        state = {}

        def get_active_files(self):
            return [
                {
                    "document_id": "old-code",
                    "url": "/storage/app.py",
                    "name": "app.py",
                    "mime": "text/x-python",
                    "active": True,
                    "legacy": False,
                },
                {
                    "document_id": "new-audio",
                    "url": "/storage/audio.wav",
                    "name": "audio.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
            ]

    url = service._resolve_input_url(
        {"selected_document_ids": ["new-audio"]},
        Session(),
    )
    assert url == "/storage/audio.wav"


def test_audio_fallback_ignores_non_audio_active_files():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    class Session:
        state = {}

        def get_active_files(self):
            return [
                {
                    "document_id": "old-code",
                    "url": "/storage/app.py",
                    "name": "app.py",
                    "mime": "text/x-python",
                    "active": True,
                    "legacy": False,
                },
                {
                    "document_id": "new-audio",
                    "url": "/storage/audio.wav",
                    "name": "audio.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
            ]

    url = service._resolve_input_url({}, Session())
    assert url == "/storage/audio.wav"


def test_selected_non_audio_document_is_rejected():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    class Session:
        state = {}

        def get_active_files(self):
            return [
                {
                    "document_id": "code",
                    "url": "/storage/app.py",
                    "name": "app.py",
                    "mime": "text/x-python",
                    "active": True,
                    "legacy": False,
                }
            ]

    with pytest.raises(ValueError, match="فایل انتخاب‌شده"):
        service._resolve_input_url(
            {"selected_document_ids": ["code"]},
            Session(),
        )


def test_rejects_arbitrary_local_paths():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )
    with pytest.raises(ValueError, match="فضای امن سامانه"):
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


def test_transcription_cache_key_changes_with_provider_or_options():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    class Core:
        pass

    gateway = type("Gateway", (), {"core": Core})()
    media = type("Media", (), {"asset_id": "asset-1"})()
    context = FakeContext(
        metadata={"media_intelligence_provider_policy": {"transcription": "asr-a"}}
    )
    first = service._transcription_cache_key(
        gateway, media, {"transcription_options": {"model": "m1"}}, context
    )
    second = service._transcription_cache_key(
        gateway, media, {"transcription_options": {"model": "m2"}}, context
    )
    third_context = FakeContext(
        metadata={"media_intelligence_provider_policy": {"transcription": "asr-b"}}
    )
    third = service._transcription_cache_key(
        gateway, media, {"transcription_options": {"model": "m1"}}, third_context
    )
    assert first != second
    assert first != third
