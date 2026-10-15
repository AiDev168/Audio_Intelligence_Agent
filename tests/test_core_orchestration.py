from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

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

    with pytest.raises(ValueError, match="فقط فایل‌های صوتی یا ویدئویی"):
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


def test_ask_downloadable_report_is_plain_text_and_contains_requested_answer():
    from types import SimpleNamespace

    from audio_intelligence_agent.agent import AudioIntelligenceAgent

    result = {
        "operation": "ask",
        "asset_id": "asset-1",
        "media_type": "audio/mpeg",
        "answer": {
            "question": "تحلیل کن",
            "answer": "این یک پاسخ مستند است.",
            "citations": [
                {
                    "interval": {"start": 0.0, "end": 11.47},
                    "excerpt": "متن شاهد",
                }
            ],
        },
        "evidence": {
            "spans": [
                {
                    "interval": {"start": 0.0, "end": 11.47},
                    "excerpt": "متن شاهد",
                }
            ]
        },
    }

    report = AudioIntelligenceAgent._build_downloadable_report(
        result,
        SimpleNamespace(execution_id="exec-1"),
        request_text="این فایل را تحلیل کن",
    )

    assert report["filename"] == "audio_result_ask_exec-1.txt"
    assert report["filename"].endswith(".txt")
    assert "درخواست کاربر:" in report["content"]
    assert "این فایل را تحلیل کن" in report["content"]
    assert "پاسخ تولیدشده:" in report["content"]
    assert "این یک پاسخ مستند است." in report["content"]
    assert "استنادها:" in report["content"]
    assert "متن شاهد" in report["content"]
    assert "# گزارش" not in report["content"]
    assert '"operation":' not in report["content"]


def test_transcription_export_is_plain_text_with_the_actual_transcript():
    from types import SimpleNamespace

    from audio_intelligence_agent.agent import AudioIntelligenceAgent

    report = AudioIntelligenceAgent._build_downloadable_report(
        {
            "operation": "transcribe",
            "asset_id": "asset-1",
            "source_filename": "6.mp3",
            "transcript_text": "[00:00-00:02] سلام، جلسه شروع شد.",
        },
        SimpleNamespace(execution_id="exec-2"),
        request_text="گفتار فایل را به متن تبدیل کن",
    )

    assert report["filename"] == "audio_result_transcribe_exec-2.txt"
    assert "درخواست کاربر:" in report["content"]
    assert "گفتار فایل را به متن تبدیل کن" in report["content"]
    assert "متن پیاده‌سازی‌شده:" in report["content"]
    assert "[00:00-00:02] سلام، جلسه شروع شد." in report["content"]
    assert '"operation":' not in report["content"]


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


def test_multiple_selected_audio_and_video_documents_are_resolved_in_requested_order():
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
                    "document_id": "voice",
                    "url": "/storage/voice.mp3",
                    "name": "voice.mp3",
                    "mime": "audio/mpeg",
                    "active": True,
                    "legacy": False,
                },
                {
                    "document_id": "video",
                    "url": "/storage/meeting.mp4",
                    "name": "meeting.mp4",
                    "mime": "video/mp4",
                    "active": True,
                    "legacy": False,
                },
            ]

    files = service._resolve_input_files(
        {"selected_document_ids": ["video", "voice"]},
        Session(),
    )
    assert [item["name"] for item in files] == ["meeting.mp4", "voice.mp3"]
    assert [item["document_id"] for item in files] == ["video", "voice"]


def test_video_extraction_uses_first_audio_stream_without_shell(monkeypatch, tmp_path):
    import audio_intelligence_agent.service as service_module

    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"video placeholder")
    command = []

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return None, b""

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    async def fake_create_subprocess_exec(*args, **kwargs):
        command.extend(args)
        Path(str(args[-1])).write_bytes(b"RIFF" + b"0" * 60)
        return FakeProcess()

    monkeypatch.setattr(service_module.shutil, "which", lambda _: "ffmpeg-test")
    monkeypatch.setattr(
        service_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    output_path = asyncio.run(
        service_module.AudioIntelligenceService._extract_audio_from_video(
            str(source),
            {},
        )
    )
    try:
        assert output_path.endswith(".wav")
        assert str(source) in command
        assert command[command.index("-map") + 1] == "0:a:0"
        assert "-vn" in command
        assert command[command.index("-ar") + 1] == "16000"
    finally:
        Path(output_path).unlink(missing_ok=True)


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
    assert service._resolve_operation("تحلیل کن", {}) == "analyze"
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
    assert [item["result"]["summary"]["summary"] for item in result["batch_results"]] == [
        "summary for /storage/second.wav",
        "summary for /storage/first.wav",
    ]


def test_manifest_supports_multi_select_audio_and_video_inputs():
    from audio_intelligence_agent.manifest import AGENT_MANIFEST

    file_input = AGENT_MANIFEST["params"]["properties"]["audio_file"]
    assert file_input["type"] == "array"
    assert file_input["multiple"] is True
    assert file_input["accept"] == "audio/*,video/*"
    assert file_input["items"]["format"] == "file"


def test_manifest_does_not_offer_audio_events_without_a_provider():
    from audio_intelligence_agent.manifest import AGENT_MANIFEST

    operation = AGENT_MANIFEST["params"]["properties"]["operation"]
    assert "audio_events" not in operation["enum"]


def test_report_is_created_only_after_explicit_download_request(monkeypatch):
    from dataclasses import dataclass

    import audio_intelligence_agent.agent as agent_module

    @dataclass
    class FakeEvent:
        type: str
        data: dict

    class FakeArtifactStore:
        def __init__(self):
            self.saved = []

        def save(self, filename, content):
            self.saved.append((filename, content))
            return "/storage/artifacts/" + filename

    class FakeService:
        def __init__(self, *, core_service, file_access, settings):
            pass

        async def execute(self, *, message, params, session, context):
            return {
                "operation": "analyze",
                "source_filename": "meeting.wav",
                "asset_id": "asset-meeting",
                "media_type": "audio/wav",
                "transcript_text": "[0.00-1.00] hello",
                "summary": {"summary": "The generated summary says the meeting starts now."},
                "evidence": {
                    "spans": [
                        {
                            "interval": {"start": 0.0, "end": 1.0},
                            "excerpt": "hello",
                        }
                    ]
                },
            }

    class FakeContext:
        def __init__(self, execution_id, capabilities):
            self.execution_id = execution_id
            self.agent_id = "audio_intelligence"
            self.capabilities = capabilities

        def is_cancelled(self):
            return False

    class Session:
        def __init__(self):
            self.state = {}

    monkeypatch.setattr(agent_module, "AgentEvent", FakeEvent)
    monkeypatch.setattr(agent_module, "AudioIntelligenceService", FakeService)

    agent = object.__new__(agent_module.AudioIntelligenceAgent)
    agent.settings = {}
    session = Session()
    store = FakeArtifactStore()
    normal_context = FakeContext(
        "analysis-1",
        {
            "agent_file_access": object(),
            "artifact_store": store,
            "media_intelligence_core": object(),
        },
    )

    async def collect_events(message, context):
        return [
            event
            async for event in agent.run_with_context(
                message=message,
                params={},
                session=session,
                context=context,
            )
        ]

    normal_events = asyncio.run(collect_events("Analyze the recording", normal_context))
    assert not [event for event in normal_events if event.type == "artifact"]
    assert store.saved == []
    pending = session.state["audio_intelligence"]["pending_download_report"]
    assert pending["source_filenames"] == ["meeting.wav"]
    assert pending["filename"].startswith("meeting_")
    assert pending["filename"].endswith(".txt")
    assert "درخواست کاربر:" in pending["content"]
    assert "Analyze the recording" in pending["content"]
    assert "The generated summary says the meeting starts now." in pending["content"]
    assert "[0.00-1.00] hello" in pending["content"]
    assert agent_module.AudioIntelligenceAgent._is_download_request("دانلود فایل متنی", {})
    done = next(event for event in normal_events if event.type == "done")
    assert "The generated summary says the meeting starts now." in done.data["text"]
    assert "تبدیل گفتار به متن با موفقیت انجام شد." not in done.data["text"]
    assert "دانلود فایل متنی" not in done.data["text"]
    completion_events = [
        event for event in normal_events
        if event.type == "progress" and event.data.get("stage") == "completed"
    ]
    assert completion_events
    assert all("دانلود فایل متنی" not in event.data.get("text", "") for event in completion_events)
    assert store.saved == []

    download_context = FakeContext("download-1", {"artifact_store": store})
    download_events = asyncio.run(collect_events("دانلود فایل متنی", download_context))
    artifacts = [event for event in download_events if event.type == "artifact"]

    assert len(artifacts) == 1
    assert len(store.saved) == 1
    assert store.saved[0][0].startswith("meeting_")
    assert store.saved[0][0].endswith(".txt")
    assert "The generated summary says the meeting starts now." in store.saved[0][1]
    assert "Analyze the recording" in store.saved[0][1]
    assert artifacts[0].data["meta"]["source_filename"] == "meeting.wav"
    assert artifacts[0].data["title"].startswith("meeting_")
    assert any(
        event.type == "done" and "meeting.wav" in event.data["text"] for event in download_events
    )
