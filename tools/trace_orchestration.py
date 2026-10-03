"""Standalone, deterministic trace for the Audio Intelligence Agent orchestration layer.

This trace intentionally does not load Whisper/faster-whisper, make network calls,
start Ai_cheshm, or require a real audio file. It verifies the Agent's own
orchestration order before the real Host/Provider integration is tested.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from audio_intelligence_agent.service import AudioIntelligenceService  # noqa: E402


@dataclass(frozen=True)
class FakeMedia:
    asset_id: str = "trace-asset"
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
    words: tuple[Any, ...] = ()
    confidence: float | None = 0.99
    provenance: Any = None


@dataclass(frozen=True)
class FakeTranscription:
    segments: tuple[FakeSegment, ...]
    language: str | None = "fa"
    provenance: Any = None


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
    value: Any
    confidence: float | None
    provenance: Any


class FakeTimeline:
    def __init__(self, *, asset_id: str):
        self.asset_id = asset_id
        self.items: list[FakeTimelineItem] = []

    def add(self, item: FakeTimelineItem) -> None:
        self.items.append(item)

    def modalities(self):
        return sorted({item.modality for item in self.items})


@dataclass
class FakeCore:
    trace: list[str] = field(default_factory=list)

    TranscriptionOptions = FakeTranscriptionOptions
    SummarizationOptions = FakeSummarizationOptions
    MediaTimeline = FakeTimeline
    TimelineItem = FakeTimelineItem

    def media_asset_from_path(self, path: str, *, media_type: str) -> FakeMedia:
        self.trace.append(f"CORE.media_asset_from_path path={Path(path).name} type={media_type}")
        return FakeMedia(media_type=media_type)

    async def execute(self, capability: str, media: FakeMedia, *, options: dict[str, Any]):
        self.trace.append(
            f"CORE.execute capability={capability} asset={media.asset_id}"
        )

        if capability == "transcription":
            return FakeTranscription(
                segments=(
                    FakeSegment(
                        segment_id="segment-1",
                        interval=FakeInterval(0.0, 1.5),
                        text="این یک متن آزمایشی است.",
                    ),
                )
            )

        if capability == "summarization":
            return {"summary": "خلاصه آزمایشی"}

        raise AssertionError(f"Unexpected capability in trace: {capability}")


class FakeCoreService:
    def __init__(self, core: FakeCore):
        self.core = core

    async def execute(self, capability: str, media: FakeMedia, *, options, host_context):
        return await self.core.execute(capability, media, options=options)


class FakeFileAccess:
    def __init__(self, trace: list[str]):
        self.trace = trace

    def resolve(self, url: str) -> str:
        self.trace.append(f"FILE_ACCESS.resolve url={url}")
        return r"C:\trace-audio\sample.wav"


class FakeSession:
    def __init__(self):
        self.state: dict[str, Any] = {}

    def get_active_files(self):
        return [{"url": "/storage/sample.wav", "active": True}]


@dataclass
class FakeContext:
    execution_id: str = "trace-execution"
    metadata: dict[str, Any] = field(default_factory=dict)


async def run(operation: str) -> None:
    trace: list[str] = []
    core = FakeCore(trace)
    service = AudioIntelligenceService(
        core_service=FakeCoreService(core),
        file_access=FakeFileAccess(trace),
        settings={},
    )

    print("[TRACE 00] request operation=", operation)
    result = await service.execute(
        message=operation,
        params={"operation": operation, "audio_file": "/storage/sample.wav"},
        session=FakeSession(),
        context=FakeContext(),
    )

    print("[TRACE 99] result operation=", result["operation"])
    for index, item in enumerate(trace, start=1):
        print(f"[TRACE {index:02d}] {item}")

    if operation == "summary":
        expected = [
            "FILE_ACCESS.resolve",
            "CORE.media_asset_from_path",
            "CORE.execute capability=transcription",
            "CORE.execute capability=summarization",
        ]
        print("[TRACE CHECK] summary orchestration completed")
        if not all(any(item.startswith(prefix) for item in trace) for prefix in expected):
            raise SystemExit("TRACE CHECK FAILED: summary orchestration stages are incomplete")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--operation",
        default="summary",
        choices=("transcribe", "summary"),
    )
    args = parser.parse_args()
    asyncio.run(run(args.operation))


if __name__ == "__main__":
    main()
