from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from audio_intelligence_agent.service import AudioIntelligenceService


@dataclass(frozen=True)
class FakeMedia:
    asset_id: str = "asset-1"
    media_type: str = "audio/wav"


@dataclass(frozen=True)
class FakeInterval:
    start: float
    end: float


@dataclass(frozen=True)
class FakeSegment:
    segment_id: str
    interval: FakeInterval
    text: str
    language: str | None = "fa"
    speaker_id: str | None = None
    words: tuple = ()
    confidence: float | None = 1.0
    provenance: object | None = None


@dataclass(frozen=True)
class FakeTranscription:
    segments: tuple[FakeSegment, ...]
    language: str | None = "fa"
    provenance: object | None = None


@dataclass(frozen=True)
class FakeTranscriptionOptions:
    model: str | None = None

@dataclass(frozen=True)
class FakeSummarizationOptions:
    max_sentences: int | None = None


@dataclass(frozen=True)
class FakeTimelineItem:
    item_id: str
    interval: FakeInterval
    modality: str
    kind: str
    value: object
    confidence: float | None
    provenance: object | None


class FakeTimeline:
    def __init__(self, *, asset_id: str):
        self.asset_id = asset_id
        self.items = []

    def add(self, item: FakeTimelineItem):
        self.items.append(item)

    def modalities(self):
        return sorted({item.modality for item in self.items})


class FakeCore:
    TranscriptionOptions = FakeTranscriptionOptions
    SummarizationOptions = FakeSummarizationOptions
    MediaTimeline = FakeTimeline
    TimelineItem = FakeTimelineItem

    def __init__(self):
        self.calls: list[str] = []

    def media_asset_from_path(self, path: str, *, media_type: str):
        self.calls.append("media_asset_from_path")
        return FakeMedia(media_type=media_type)

    async def execute(self, capability, media, *, options):
        self.calls.append(capability)
        if capability == "transcription":
            return FakeTranscription(
                segments=(
                    FakeSegment(
                        segment_id="segment-1",
                        interval=FakeInterval(0.0, 1.0),
                        text="trace",
                    ),
                )
            )
        if capability == "summarization":
            return {"summary": "trace summary"}
        raise AssertionError(capability)


class FakeCoreService:
    def __init__(self, core):
        self.core = core

    async def execute(self, capability, media, *, options, host_context):
        return await self.core.execute(capability, media, options=options)


class FakeFileAccess:
    def resolve(self, url: str):
        assert url == "/storage/sample.wav"
        return r"C:\sample.wav"


class FakeSession:
    def __init__(self):
        self.state = {}

    def get_active_files(self):
        return [{"url": "/storage/sample.wav", "active": True}]


@dataclass
class FakeContext:
    execution_id: str = "trace"
    metadata: dict = field(default_factory=dict)


def test_summary_orchestration_calls_transcription_before_semantic_stage():
    core = FakeCore()
    service = AudioIntelligenceService(
        core_service=FakeCoreService(core),
        file_access=FakeFileAccess(),
        settings={},
    )

    result = asyncio.run(
        service.execute(
            message="خلاصه کن",
            params={"operation": "summary", "audio_file": "/storage/sample.wav"},
            session=FakeSession(),
            context=FakeContext(),
        )
    )

    assert result["operation"] == "summary"
    assert core.calls == [
        "media_asset_from_path",
        "transcription",
        "summarization",
    ]
    assert result["timeline"]["item_count"] == 1


def test_trace_uses_protected_storage_reference():
    service = AudioIntelligenceService(
        core_service=object(),
        file_access=FakeFileAccess(),
        settings={},
    )

    assert service._validate_storage_url("/storage/sample.wav") == "/storage/sample.wav"
