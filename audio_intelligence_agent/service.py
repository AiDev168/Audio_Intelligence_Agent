"""Audio-domain orchestration for the Ai_cheshm plugin."""
from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import fields
from typing import Any

from audio_intelligence_agent.core_adapter import CoreCapabilityGateway


TRANSCRIPTION_CACHE_SCHEMA_VERSION = "1"


CAPABILITY_NAMES = {
    "transcription": "transcription",
    "language": "language-identification",
    "diarization": "diarization",
    "speaker_analysis": "speaker-turn-analysis",
    "search": "temporal-transcript-search",
    "topics": "topic-chapter",
    "summary": "summarization",
    "entities": "entity-extraction",
    "audio_events": "audio-event",
    "evidence": "audio-evidence",
    "qa": "grounded-qa",
}


def _construct_option(option_type: Any, raw: dict[str, Any] | None = None) -> Any:
    """Construct a Core dataclass using only fields its current contract defines."""
    values = dict(raw or {})
    allowed = {item.name for item in fields(option_type)}
    filtered = {key: value for key, value in values.items() if key in allowed}
    for key in ("candidate_languages", "entity_types", "event_types"):
        if key in filtered and isinstance(filtered[key], list):
            filtered[key] = tuple(str(value) for value in filtered[key])
    return option_type(**filtered)


def _serialize_provenance(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "source_asset_id": value.source_asset_id,
        "operation": value.operation,
        "provider": value.provider,
        "provider_version": value.provider_version,
        "model": value.model,
        "model_version": value.model_version,
        "parameters": value.parameters,
        "core_schema_version": value.core_schema_version,
    }


def _serialize_transcription(result: Any) -> dict[str, Any]:
    return {
        "language": result.language,
        "provenance": _serialize_provenance(result.provenance),
        "segments": [
            {
                "segment_id": item.segment_id,
                "start": item.interval.start,
                "end": item.interval.end,
                "text": item.text,
                "language": item.language,
                "speaker_id": item.speaker_id,
                "words": list(item.words),
                "confidence": item.confidence,
            }
            for item in result.segments
        ],
    }


class AudioIntelligenceService:
    """User-facing workflow over provider-neutral Media Core contracts."""

    def __init__(self, *, core_service: Any, file_access: Any, settings: dict[str, Any]):
        self.core_service = core_service
        self.file_access = file_access
        self.settings = dict(settings)

    async def execute(
        self,
        *,
        message: str,
        params: dict[str, Any],
        session: Any,
        context: Any,
    ) -> dict[str, Any]:
        prepared = dict(self.settings)
        prepared.update(params or {})

        operation = self._resolve_operation(message, prepared)
        input_url = self._resolve_input_url(prepared, session)
        resolved_path = self.file_access.resolve(input_url)

        core = CoreCapabilityGateway(self.core_service, context)
        media = core.core.media_asset_from_path(
            resolved_path,
            media_type=self._media_type(resolved_path),
        )

        result: dict[str, Any] = {
            "operation": operation,
            "asset_id": media.asset_id,
            "media_type": media.media_type,
            "profile": prepared.get("profile", "general"),
        }

        transcription = None
        if operation in {
            "transcribe",
            "analyze",
            "diarize",
            "speaker_analysis",
            "search",
            "topics",
            "summary",
            "entities",
            "audio_events",
            "evidence",
            "ask",
        }:
            transcription = await self._get_transcription(
                core, media, prepared, session, context
            )
            result["transcription"] = self._to_public(transcription)
            result["transcript_text"] = self._transcript_text(transcription)

        if operation in {"language", "analyze"}:
            language = await core.execute(
                CAPABILITY_NAMES["language"],
                media,
                options={
                    "language_options": _construct_option(
                        core.core.LanguageIdentificationOptions,
                        prepared.get("language_options"),
                    )
                },
            )
            result["language"] = self._to_public(language)

        diarization = None
        if operation in {"diarize", "speaker_analysis", "analyze"}:
            diarization = await self._get_diarization(core, media, prepared)
            result["diarization"] = self._to_public(diarization)

            if operation in {"speaker_analysis", "analyze"}:
                speaker_result = await core.execute(
                    CAPABILITY_NAMES["speaker_analysis"],
                    media,
                    options={
                        "transcription": transcription,
                        "diarization": diarization,
                        "speaker_options": _construct_option(
                            core.core.SpeakerAttributionOptions,
                            prepared.get("speaker_options"),
                        ),
                    },
                )
                result["speaker_analysis"] = self._to_public(speaker_result)

        if operation == "search":
            query_text = str(prepared.get("query") or message).strip()
            query = _construct_option(
                core.core.TranscriptSearchQuery,
                {"text": query_text, **(prepared.get("search_options") or {})},
            )
            search_result = await core.execute(
                CAPABILITY_NAMES["search"],
                media,
                options={"transcription": transcription, "query": query},
            )
            result["search"] = self._to_public(search_result)

        if operation in {"topics", "analyze"}:
            topics = await core.execute(
                CAPABILITY_NAMES["topics"],
                media,
                options={
                    "transcription": transcription,
                    "topic_options": _construct_option(
                        core.core.TopicChapterOptions,
                        prepared.get("topic_options"),
                    ),
                },
            )
            result["topics"] = self._to_public(topics)

        if operation in {"summary", "analyze"}:
            summary = await core.execute(
                CAPABILITY_NAMES["summary"],
                media,
                options={
                    "transcription": transcription,
                    "summary_options": _construct_option(
                        core.core.SummarizationOptions,
                        prepared.get("summary_options"),
                    ),
                },
            )
            result["summary"] = self._to_public(summary)

        if operation in {"entities", "analyze"}:
            entities = await core.execute(
                CAPABILITY_NAMES["entities"],
                media,
                options={
                    "transcription": transcription,
                    "entity_options": _construct_option(
                        core.core.EntityExtractionOptions,
                        prepared.get("entity_options"),
                    ),
                },
            )
            result["entities"] = self._to_public(entities)

        events = None
        if operation in {"audio_events", "evidence", "ask", "analyze"}:
            events = await core.execute(
                CAPABILITY_NAMES["audio_events"],
                media,
                options={
                    "event_options": _construct_option(
                        core.core.AudioEventOptions,
                        prepared.get("audio_event_options"),
                    )
                },
            )
            result["audio_events"] = self._to_public(events)

        if operation == "evidence":
            evidence_query = self._make_evidence_query(
                core,
                str(prepared.get("query") or message).strip(),
                prepared,
            )
            evidence = await core.execute(
                CAPABILITY_NAMES["evidence"],
                media,
                options={
                    "evidence_query": evidence_query,
                    "transcription": transcription,
                    "audio_events": events,
                },
            )
            result["evidence"] = self._to_public(evidence)

        if operation == "ask":
            question = str(prepared.get("query") or message).strip()
            evidence_query = self._make_evidence_query(core, question, prepared)
            evidence = await core.execute(
                CAPABILITY_NAMES["evidence"],
                media,
                options={
                    "evidence_query": evidence_query,
                    "transcription": transcription,
                    "audio_events": events,
                },
            )
            result["evidence"] = self._to_public(evidence)
            answer = await core.execute(
                CAPABILITY_NAMES["qa"],
                media,
                options={
                    "question": question,
                    "evidence": evidence,
                    "qa_options": _construct_option(
                        core.core.GroundedQAOptions,
                        prepared.get("qa_options"),
                    ),
                },
            )
            result["answer"] = self._to_public(answer)

        if operation in {
            "transcribe",
            "language",
            "diarize",
            "speaker_analysis",
            "search",
            "topics",
            "summary",
            "entities",
            "audio_events",
            "evidence",
            "ask",
            "analyze",
        }:
            result["timeline"] = self._timeline_summary(
                core,
                media,
                transcription,
                diarization,
                events,
            )

        return result

    def _resolve_input_url(self, params: dict[str, Any], session: Any) -> str:
        for key in ("audio_file", "input_file", "file"):
            value = str(params.get(key) or "").strip()
            if value:
                return self._validate_storage_url(value)

        active_files = session.get_active_files() if hasattr(session, "get_active_files") else []
        if active_files:
            return self._validate_storage_url(str(active_files[0].get("url") or ""))

        raise ValueError("Please upload an audio file first.")

    @staticmethod
    def _validate_storage_url(value: str) -> str:
        if not value.startswith("/storage/"):
            raise ValueError("Audio Intelligence accepts only platform storage URLs.")

        return value

    @staticmethod
    def _media_type(path: str) -> str:
        return mimetypes.guess_type(path)[0] or "audio/unknown"

    def _resolve_operation(self, message: str, params: dict[str, Any]) -> str:
        operation = str(params.get("operation") or "").strip().lower()
        if operation:
            aliases = {
                "transcription": "transcribe",
                "transcript": "transcribe",
                "language_id": "language",
                "speaker": "speaker_analysis",
                "chapters": "topics",
                "summarize": "summary",
                "entities_keywords": "entities",
                "events": "audio_events",
                "qa": "ask",
                "question": "ask",
            }
            return aliases.get(operation, operation)

        text = f"{message} {params.get('query') or ''}".lower()
        if any(token in text for token in ("summary", "summarize", "خلاصه", "خلاصه کن")):
            return "summary"
        if any(token in text for token in ("transcript", "transcribe", "پیاده", "متن")):
            return "transcribe"
        if any(token in text for token in ("who spoke", "speaker", "گوینده", "چه کسی صحبت")):
            return "speaker_analysis"
        if any(token in text for token in ("language", "زبان")):
            return "language"
        if any(token in text for token in ("chapter", "topic", "فصل", "موضوع")):
            return "topics"
        return "ask"

    async def _get_transcription(self, core, media, prepared, session, context):
        cache_enabled = bool(prepared.get("cache_enabled", True))
        if cache_enabled:
            cached = self._cached_transcription(core, media, prepared, session, context)
            if cached is not None:
                return cached

        result = await core.execute(
            CAPABILITY_NAMES["transcription"],
            media,
            options={
                "transcription_options": _construct_option(
                    core.core.TranscriptionOptions,
                    prepared.get("transcription_options"),
                )
            },
        )
        if cache_enabled:
            state = session.state.setdefault("audio_intelligence", {})
            assets = state.setdefault("assets", {})
            cache_key = self._transcription_cache_key(core, media, prepared, context)
            assets[cache_key] = {
                "asset_id": media.asset_id,
                "transcription": _serialize_transcription(result),
            }
        return result

    def _make_evidence_query(self, core, query_text: str, prepared):
        options = dict(prepared.get("evidence_options") or {})
        options.setdefault(
            "limit",
            int(prepared.get("evidence_limit", self.settings.get("evidence_limit", 20))),
        )
        options["query"] = query_text
        return _construct_option(core.core.AudioEvidenceQuery, options)

    def _timeline_summary(self, core, media, transcription, diarization, audio_events):
        timeline = core.core.MediaTimeline(asset_id=media.asset_id)
        timeline_item = core.core.TimelineItem
        for segment in getattr(transcription, "segments", ()):
            timeline.add(
                timeline_item(
                    item_id=segment.segment_id,
                    interval=segment.interval,
                    modality="audio",
                    kind="transcript",
                    value=segment,
                    confidence=segment.confidence,
                    provenance=segment.provenance,
                )
            )
        for turn in getattr(diarization, "turns", ()):
            timeline.add(
                timeline_item(
                    item_id=turn.turn_id,
                    interval=turn.interval,
                    modality="speaker",
                    kind="speaker_turn",
                    value=turn,
                    confidence=turn.confidence,
                    provenance=turn.provenance,
                )
            )
        for event in getattr(audio_events, "events", ()):
            timeline.add(
                timeline_item(
                    item_id=event.event_id,
                    interval=event.interval,
                    modality="audio_event",
                    kind="audio_event",
                    value=event,
                    confidence=event.confidence,
                    provenance=event.provenance,
                )
            )
        return {
            "asset_id": timeline.asset_id,
            "item_count": len(timeline.items),
            "modalities": list(timeline.modalities()),
        }

    def _transcription_cache_key(self, core, media, prepared, context) -> str:
        options = prepared.get("transcription_options") or {}
        policy = context.metadata.get("media_intelligence_provider_policy", {})
        payload = {
            "schema_version": TRANSCRIPTION_CACHE_SCHEMA_VERSION,
            "asset_id": media.asset_id,
            "capability": CAPABILITY_NAMES["transcription"],
            "provider": policy.get(CAPABILITY_NAMES["transcription"]),
            "options": options,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _cached_transcription(self, core, media, prepared, session, context):
        state = session.state.get("audio_intelligence") or {}
        cache_key = self._transcription_cache_key(core, media, prepared, context)
        record = (state.get("assets") or {}).get(cache_key) or {}
        payload = record.get("transcription")
        if not payload:
            return None

        try:
            provenance = None
            if payload.get("provenance"):
                provenance = core.core.Provenance(**payload["provenance"])
            segments = [
                core.core.TranscriptSegment(
                    segment_id=item["segment_id"],
                    interval=core.core.MediaInterval(float(item["start"]), float(item["end"])),
                    text=item["text"],
                    language=item.get("language"),
                    speaker_id=item.get("speaker_id"),
                    words=tuple(item.get("words") or ()),
                    confidence=item.get("confidence"),
                    provenance=provenance,
                )
                for item in payload["segments"]
            ]
            return core.core.TranscriptionResult(
                segments=tuple(segments),
                language=payload.get("language"),
                provenance=provenance,
            )
        except Exception:
            state.get("assets", {}).pop(media.asset_id, None)
            return None

    async def _get_diarization(self, core, media, prepared):
        return await core.execute(
            CAPABILITY_NAMES["diarization"],
            media,
            options={
                "diarization_options": _construct_option(
                    core.core.DiarizationOptions,
                    prepared.get("diarization_options"),
                )
            },
        )

    @staticmethod
    def _transcript_text(result: Any) -> str:
        return "\n".join(
            f"[{item.interval.start:.2f}-{item.interval.end:.2f}] {item.text}"
            for item in result.segments
        )

    @staticmethod
    def _to_public(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): AudioIntelligenceService._to_public(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [AudioIntelligenceService._to_public(item) for item in value]
        if hasattr(value, "__dataclass_fields__"):
            return {
                field.name: AudioIntelligenceService._to_public(getattr(value, field.name))
                for field in fields(value)
            }
        if hasattr(value, "__dict__"):
            return {
                str(key): AudioIntelligenceService._to_public(item)
                for key, item in vars(value).items()
                if not str(key).startswith("_")
            }
        return str(value)


__all__ = ["AudioIntelligenceService", "CAPABILITY_NAMES"]
