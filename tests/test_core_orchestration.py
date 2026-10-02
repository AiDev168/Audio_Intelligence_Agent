from __future__ import annotations

from dataclasses import dataclass, field

import pytest

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
