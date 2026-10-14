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


def test_ask_downloadable_report_is_human_readable_markdown():
    from types import SimpleNamespace

    from audio_intelligence_agent.agent import AudioIntelligenceAgent

    result = {
        "operation": "ask",
        "asset_id": "asset-1",
        "media_type": "audio/mpeg",
        "transcript_text": "[0.00-11.47] متن صوت",
        "evidence": {
            "spans": [
                {
                    "interval": {"start": 0.0, "end": 11.47},
                    "excerpt": "متن صوت",
                }
            ]
        },
        "answer": {
            "question": "تحلیل کن",
            "answer": "این یک پاسخ مستند است.",
            "citations": [
                {
                    "interval": {"start": 0.0, "end": 11.47},
                    "excerpt": "متن صوت",
                }
            ],
        },
    }

    report = AudioIntelligenceAgent._build_downloadable_report(
        result,
        SimpleNamespace(execution_id="exec-1"),
    )

    assert report["filename"] == "audio_ask_exec-1.md"
    assert "# گزارش تحلیل صوتی" in report["content"]
    assert "## پرسش" in report["content"]
    assert "تحلیل کن" in report["content"]
    assert "## پاسخ" in report["content"]
    assert "این یک پاسخ مستند است." in report["content"]
    assert "## متن پیاده‌سازی‌شده" in report["content"]
    assert "## شواهد و استنادها" in report["content"]
    assert ".json" not in report["filename"]


def test_non_ask_downloadable_report_keeps_legacy_structured_json():
    from types import SimpleNamespace

    from audio_intelligence_agent.agent import AudioIntelligenceAgent

    report = AudioIntelligenceAgent._build_downloadable_report(
        {"operation": "transcribe", "asset_id": "asset-1"},
        SimpleNamespace(execution_id="exec-2"),
    )

    assert report["filename"] == "audio_analysis_exec-2.json"
    assert '"operation": "transcribe"' in report["content"]



def test_multiple_selected_audio_documents_are_resolved_in_requested_order():
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
                    "document_id": "first",
                    "url": "/storage/first.wav",
                    "name": "first.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
                {
                    "document_id": "second",
                    "url": "/storage/second.mp3",
                    "name": "second.mp3",
                    "mime": "audio/mpeg",
                    "active": True,
                    "legacy": False,
                },
            ]

    files = service._resolve_input_files(
        {"selected_document_ids": ["second", "first"]},
        Session(),
    )
    assert [item["document_id"] for item in files] == ["second", "first"]
    assert [item["url"] for item in files] == [
        "/storage/second.mp3",
        "/storage/first.wav",
    ]


def test_multiple_active_audio_files_are_never_silently_resolved_to_the_last_one():
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
                    "document_id": "old",
                    "url": "/storage/old.wav",
                    "name": "old.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
                {
                    "document_id": "new",
                    "url": "/storage/new.wav",
                    "name": "new.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
            ]

    with pytest.raises(ValueError, match="جلوگیری از تحلیل فایل اشتباه"):
        service._resolve_input_files({}, Session())


def test_transcription_cache_key_includes_file_content_digest():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    class Core:
        pass

    gateway = type("Gateway", (), {"core": Core})()
    media = type("Media", (), {"asset_id": "same-asset-id"})()
    context = FakeContext(
        metadata={"media_intelligence_provider_policy": {"transcription": "asr-a"}}
    )
    first = service._transcription_cache_key(
        gateway, media, {"audio_content_sha256": "content-a"}, context
    )
    second = service._transcription_cache_key(
        gateway, media, {"audio_content_sha256": "content-b"}, context
    )
    assert first != second



def test_markdown_report_discloses_unavailable_optional_capabilities():
    from types import SimpleNamespace

    from audio_intelligence_agent.agent import AudioIntelligenceAgent

    report = AudioIntelligenceAgent._build_downloadable_report(
        {
            "operation": "analyze",
            "asset_id": "asset-1",
            "media_type": "audio/wav",
            "transcript_text": "سلام",
            "diarization_status": "unavailable",
            "diarization_diagnostic": "No local diarization model configured",
            "audio_events_status": "unavailable",
            "audio_events_diagnostic": "No provider configured",
        },
        SimpleNamespace(execution_id="exec-status"),
    )

    assert "وضعیت قابلیت‌های تکمیلی" in report["content"]
    assert "تفکیک گویندگان" in report["content"]
    assert "در دسترس نیست" in report["content"]
    assert "تشخیص رویدادهای صوتی" in report["content"]



def test_natural_phrase_analyze_resolves_to_full_analysis():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    assert service._resolve_operation("این فایل را تحلیل کن", {}) == "analyze"
    assert service._resolve_operation("تحلیل کامل انجام بده", {}) == "analyze"
    assert service._resolve_operation("این صوت درباره چه چیزی است؟", {}) == "ask"



def test_execute_aggregates_multiple_audio_files_in_selected_order():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )
    processed = []

    async def fake_execute_single(*, message, params, session, context):
        url = params["audio_file"]
        processed.append(url)
        return {
            "asset_id": f"asset-{len(processed)}",
            "operation": "summary",
            "summary": {"summary": f"summary for {url}"},
        }

    service._execute_single = fake_execute_single

    class Session:
        state = {}

        def get_active_files(self):
            return [
                {
                    "document_id": "audio-first",
                    "url": "/storage/first.wav",
                    "name": "first.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
                {
                    "document_id": "audio-second",
                    "url": "/storage/second.wav",
                    "name": "second.wav",
                    "mime": "audio/wav",
                    "active": True,
                    "legacy": False,
                },
            ]

    result = asyncio.run(
        service.execute(
            message="خلاصه کن",
            params={"selected_document_ids": ["audio-second", "audio-first"]},
            session=Session(),
            context=FakeContext(),
        )
    )

    assert result["operation"] == "summary"
    assert result["asset_count"] == 2
    assert result["source_filenames"] == ["second.wav", "first.wav"]
    assert processed == ["/storage/second.wav", "/storage/first.wav"]
    assert [
        item["result"]["summary"]["summary"] for item in result["batch_results"]
    ] == [
        "summary for /storage/second.wav",
        "summary for /storage/first.wav",
    ]


def test_manifest_does_not_offer_audio_events_without_a_provider():
    from audio_intelligence_agent.manifest import AGENT_MANIFEST

    operation = AGENT_MANIFEST["params"]["properties"]["operation"]
    assert "audio_events" not in operation["enum"]
