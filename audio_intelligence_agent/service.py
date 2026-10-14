"""Audio-domain orchestration for the Ai_cheshm plugin."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from dataclasses import fields
from typing import Any

from audio_intelligence_agent.core_adapter import CoreCapabilityError, CoreCapabilityGateway

TRANSCRIPTION_CACHE_SCHEMA_VERSION = "3"


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
        audio_files = self._resolve_input_files(prepared, session)
        operation = self._resolve_operation(message, prepared)

        if len(audio_files) == 1:
            single_params = dict(params or {})
            single_params["audio_file"] = audio_files[0]["url"]
            result = await self._execute_single(
                message=message,
                params=single_params,
                session=session,
                context=context,
            )
            result.setdefault("source_filename", audio_files[0]["name"])
            return result

        batch_results: list[dict[str, Any]] = []
        for audio_file in audio_files:
            if hasattr(context, "is_cancelled") and context.is_cancelled():
                break
            single_params = dict(params or {})
            single_params["audio_file"] = audio_file["url"]
            single_result = await self._execute_single(
                message=message,
                params=single_params,
                session=session,
                context=context,
            )
            batch_results.append(
                {
                    "filename": audio_file["name"],
                    "document_id": audio_file["document_id"],
                    "asset_id": single_result.get("asset_id"),
                    "result": single_result,
                }
            )

        return {
            "operation": operation,
            "batch_results": batch_results,
            "asset_count": len(batch_results),
            "asset_ids": [
                item["asset_id"] for item in batch_results if item.get("asset_id")
            ],
            "source_filenames": [item["filename"] for item in batch_results],
        }

    async def _execute_single(
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
        prepared["audio_content_sha256"] = self._sha256_file(resolved_path)

        core = CoreCapabilityGateway(self.core_service, context)
        media = core.core.media_asset_from_path(
            resolved_path,
            media_type=self._media_type(resolved_path),
        )

        trace_enabled = os.getenv("AUDIO_INTELLIGENCE_TRACE", "").strip() == "1"
        if trace_enabled:
            print(
                f"[AGENT TRACE] service:operation={operation} asset_id={media.asset_id}",
                flush=True,
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
            transcription = await self._get_transcription(core, media, prepared, session, context)
            if trace_enabled:
                print("[AGENT TRACE] transcription:service_result_received", flush=True)
            result["transcription"] = self._to_public(transcription)
            if trace_enabled:
                print("[AGENT TRACE] transcription:public_conversion_done", flush=True)
            result["transcript_text"] = self._transcript_text(transcription)
            if trace_enabled:
                print("[AGENT TRACE] transcription:text_conversion_done", flush=True)

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
            try:
                diarization = await self._get_diarization(core, media, prepared)
                result["diarization_status"] = "ok"
                result["diarization"] = self._to_public(diarization)
            except CoreCapabilityError as exc:
                if operation != "analyze":
                    raise
                result["diarization_status"] = "unavailable"
                result["diarization_diagnostic"] = exc.detail

            if operation in {"speaker_analysis", "analyze"}:
                if diarization is None:
                    result["speaker_analysis_status"] = "skipped_diarization_unavailable"
                else:
                    try:
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
                        result["speaker_analysis_status"] = "ok"
                        result["speaker_analysis"] = self._to_public(speaker_result)
                    except CoreCapabilityError as exc:
                        if operation != "analyze":
                            raise
                        result["speaker_analysis_status"] = "unavailable"
                        result["speaker_analysis_diagnostic"] = exc.detail

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
        if operation in {"audio_events", "analyze"}:
            try:
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
                result["audio_events_status"] = "ok"
                result["audio_events"] = self._to_public(events)
            except CoreCapabilityError as exc:
                if operation != "analyze":
                    raise
                result["audio_events_status"] = "unavailable"
                result["audio_events_diagnostic"] = exc.detail

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
            if trace_enabled:
                print(
                    "[AGENT TRACE] timeline:built "
                    f"items={result['timeline']['item_count']}",
                    flush=True,
                )

        if trace_enabled:
            print("[AGENT TRACE] service:return", flush=True)
        return result

    def _resolve_input_files(
        self,
        params: dict[str, Any],
        session: Any,
    ) -> list[dict[str, str]]:
        active_files = (
            session.get_active_files() if hasattr(session, "get_active_files") else []
        )
        by_url = {
            str(item.get("url") or ""): item
            for item in active_files
            if str(item.get("url") or "")
        }

        for key in ("audio_files", "audio_file", "input_file", "file"):
            raw_value = params.get(key)
            if raw_value is None or raw_value == "":
                continue
            values = raw_value if isinstance(raw_value, (list, tuple)) else [raw_value]
            resolved = []
            for value in values:
                if isinstance(value, dict):
                    url = str(value.get("url") or value.get("value") or "").strip()
                    supplied_name = str(value.get("name") or "").strip()
                else:
                    url = str(value or "").strip()
                    supplied_name = ""
                if not url:
                    continue
                url = self._validate_storage_url(url)
                item = by_url.get(url, {})
                if item and not self._is_audio_file(item):
                    raise ValueError(
                        f"فایل «{item.get('name') or url}» فایل صوتی شناخته‌شده‌ای نیست."
                    )
                name = supplied_name or str(item.get("name") or url.rsplit("/", 1)[-1])
                resolved.append(
                    {
                        "url": url,
                        "name": name,
                        "document_id": str(item.get("document_id") or ""),
                    }
                )
            if resolved:
                return self._deduplicate_input_files(resolved)

        raw_selected = params.get("selected_document_ids") or []
        if isinstance(raw_selected, str):
            selected_ids = [raw_selected.strip()] if raw_selected.strip() else []
        else:
            selected_ids = list(dict.fromkeys(
                str(item).strip() for item in raw_selected if str(item).strip()
            ))
        if selected_ids:
            by_id = {
                str(item.get("document_id") or ""): item
                for item in active_files
                if str(item.get("document_id") or "")
            }
            missing = [item for item in selected_ids if item not in by_id]
            if missing:
                raise ValueError(
                    "یک یا چند فایل انتخاب‌شده دیگر در نشست فعال نیستند؛ فهرست «اسناد من» را تازه کنید."
                )
            selected_audio = [by_id[item] for item in selected_ids]
            not_audio = [
                str(item.get("name") or "فایل")
                for item in selected_audio
                if not self._is_audio_file(item)
            ]
            if not_audio:
                raise ValueError(
                    "برای تحلیل صوتی فقط فایل صوتی انتخاب کنید: " + "، ".join(not_audio[:5])
                )
            return self._deduplicate_input_files(
                [
                    {
                        "url": self._validate_storage_url(str(item.get("url") or "")),
                        "name": str(item.get("name") or "فایل صوتی"),
                        "document_id": str(item.get("document_id") or ""),
                    }
                    for item in selected_audio
                ]
            )

        audio_files = [item for item in active_files if self._is_audio_file(item)]
        if len(audio_files) == 1:
            item = audio_files[0]
            return [{
                "url": self._validate_storage_url(str(item.get("url") or "")),
                "name": str(item.get("name") or "فایل صوتی"),
                "document_id": str(item.get("document_id") or ""),
            }]
        if len(audio_files) > 1:
            raise ValueError(
                "چند فایل صوتی در نشست وجود دارد. برای جلوگیری از تحلیل فایل اشتباه، "
                "از «اسناد من» یک یا چند فایل را انتخاب کنید."
            )
        raise ValueError("لطفاً ابتدا یک فایل صوتی را بارگذاری یا برای تحلیل انتخاب کنید.")

    @staticmethod
    def _deduplicate_input_files(files: list[dict[str, str]]) -> list[dict[str, str]]:
        unique: dict[str, dict[str, str]] = {}
        for item in files:
            unique.setdefault(item["url"], item)
        if not unique:
            raise ValueError("لطفاً حداقل یک فایل صوتی را برای تحلیل انتخاب کنید.")
        return list(unique.values())

    def _resolve_input_url(self, params: dict[str, Any], session: Any) -> str:
        files = self._resolve_input_files(params, session)
        if len(files) != 1:
            raise ValueError("برای این مرحله باید دقیقاً یک فایل صوتی مشخص شده باشد.")
        return files[0]["url"]

    @staticmethod
    def _sha256_file(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _is_audio_file(item: dict[str, Any]) -> bool:
        mime = str(item.get("mime") or "").strip().lower()
        if mime.startswith("audio/"):
            return True
        for value in (item.get("name"), item.get("url")):
            guessed = mimetypes.guess_type(str(value or ""))[0]
            if guessed and guessed.startswith("audio/"):
                return True
        return False

    @staticmethod
    def _validate_storage_url(value: str) -> str:
        if not value.startswith("/storage/"):
            raise ValueError("این ایجنت فقط فایل‌های بارگذاری‌شده در فضای امن سامانه را می‌پذیرد.")

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

        trace_enabled = str(__import__("os").getenv("AUDIO_INTELLIGENCE_TRACE", "")).strip() == "1"
        if trace_enabled:
            print("[AGENT TRACE] transcription:core_execute:start", flush=True)
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
        if trace_enabled:
            print(
                "[AGENT TRACE] transcription:core_execute:done "
                f"segments={len(getattr(result, "segments", ()))}, "
                f"language={getattr(result, "language", None)!s}",
                flush=True,
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
            "content_sha256": prepared.get("audio_content_sha256"),
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
            (state.get("assets") or {}).pop(cache_key, None)
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
