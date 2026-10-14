"""Ai_cheshm plugin entry point for Audio Intelligence."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from .core_adapter import CoreCapabilityError
from .manifest import AGENT_MANIFEST
from .service import AudioIntelligenceService

try:
    from core.base_agent import BaseAgent, Manifest
    from core.events import AgentEvent
    from core.platform.contracts import ExecutionContext
    from core.session import Session
except ImportError:
    BaseAgent = object  # type: ignore[assignment,misc]
    Manifest = None  # type: ignore[assignment,misc]
    AgentEvent = Any  # type: ignore[assignment,misc]
    ExecutionContext = Any  # type: ignore[assignment,misc]
    Session = Any  # type: ignore[assignment,misc]


logger = logging.getLogger("audio_intelligence_agent")


_CAPABILITY_LABELS = {
    "transcription": "تبدیل گفتار به متن",
    "language-identification": "تشخیص زبان",
    "diarization": "تفکیک گویندگان",
    "speaker-turn-analysis": "تحلیل گویندگان",
    "temporal-transcript-search": "جست‌وجو در متن صوت",
    "topic-chapter": "موضوعات و فصل‌ها",
    "summarization": "خلاصه‌سازی",
    "entity-extraction": "استخراج موجودیت‌ها",
    "audio-event": "تشخیص رویدادهای صوتی",
    "audio-evidence": "استخراج شواهد زمانی",
    "grounded-qa": "پرسش و پاسخ مستند",
}


def _error_hint(capability: str | None) -> str:
    hints = {
        "transcription": (
            "مسیر مدل faster-whisper، وجود faster-whisper در همان Python، "
            "device/compute type و دسترسی فایل صوتی را بررسی کنید."
        ),
        "summarization": (
            "Base URL، API Key و نام مدل زبانی را بررسی کنید و مطمئن شوید "
            "سرویس ریموت endpoint سازگار با /chat/completions دارد."
        ),
        "topic-chapter": (
            "تنظیمات مدل زبانی و دسترسی سرویس به /chat/completions را بررسی کنید."
        ),
        "entity-extraction": (
            "تنظیمات مدل زبانی و پاسخ JSON سرویس را بررسی کنید."
        ),
        "grounded-qa": (
            "تنظیمات مدل زبانی را بررسی کنید؛ Provider باید پاسخ JSON شامل "
            "answer و citations برگرداند."
        ),
        "diarization": (
            "توکن Hugging Face، دسترسی مدل pyannote و سازگاری device را بررسی کنید."
        ),
        "audio-event": (
            "Provider تولیدی تشخیص رویدادهای صوتی هنوز در Host assembly فعال نشده است."
        ),
    }
    return hints.get(
        str(capability or ""),
        "جزئیات فنی و تنظیمات Provider این قابلیت را بررسی کنید.",
    )


class AudioIntelligenceAgent(BaseAgent):
    """User-facing Audio Intelligence plugin."""

    if Manifest is not None:
        manifest = Manifest(**AGENT_MANIFEST)
    else:
        manifest = AGENT_MANIFEST

    async def run_with_context(
        self,
        message: str,
        params: dict[str, Any],
        session: Session,
        context: ExecutionContext,
    ) -> AsyncIterator[AgentEvent]:
        if context.is_cancelled():
            yield AgentEvent(type="cancelled", data={"execution_id": context.execution_id})
            return

        if not str(message or "").strip() and not any(
            str(params.get(key) or "").strip() for key in ("operation", "query", "audio_file")
        ):
            yield AgentEvent(
                type="error",
                data={
                    "text": "لطفاً درخواست صوتی خود را وارد کنید.",
                    "execution_id": context.execution_id,
                },
            )
            return

        file_access = context.capabilities.get("agent_file_access")
        artifact_store = context.capabilities.get("artifact_store")
        media_core = context.capabilities.get("media_intelligence_core")
        missing = [
            name
            for name, value in (
                ("agent_file_access", file_access),
                ("artifact_store", artifact_store),
                ("media_intelligence_core", media_core),
            )
            if value is None
        ]
        if missing:
            yield AgentEvent(
                type="error",
                data={
                    "text": "تحلیلگر هوشمند صوتی در پلتفرم به‌طور کامل تنظیم نشده است.",
                    "execution_id": context.execution_id,
                    "missing_capability_count": len(missing),
                },
            )
            return

        yield AgentEvent(
            type="thinking",
            data={
                "text": "در حال آماده‌سازی تحلیل صوتی...",
                "execution_id": context.execution_id,
            },
        )

        try:
            service = AudioIntelligenceService(
                core_service=media_core,
                file_access=file_access,
                settings=self.settings,
            )
            result = await service.execute(
                message=str(message or ""),
                params=dict(params or {}),
                session=session,
                context=context,
            )
        except (ValueError, FileNotFoundError, PermissionError) as exc:
            logger.exception(
                "Audio input/workflow failure: execution_id=%s error_type=%s",
                context.execution_id,
                type(exc).__name__,
            )
            yield AgentEvent(
                type="error",
                data={
                    "text": str(exc),
                    "execution_id": context.execution_id,
                    "error_code": "audio_input_or_workflow_error",
                    "stage": "input_or_workflow",
                    "cause_type": type(exc).__name__,
                    "detail": str(exc)[:1200],
                    "hint": (
                        "فایل صوتی، دسترسی آن و operation/پارامترهای درخواست را بررسی کنید."
                    ),
                },
            )
            return
        except CoreCapabilityError as exc:
            logger.exception(
                "Audio execution failed: execution_id=%s capability=%s error_type=%s",
                context.execution_id,
                exc.capability or "unknown",
                exc.cause_type or type(exc).__name__,
            )
            capability = exc.capability
            label = _CAPABILITY_LABELS.get(capability or "", "تحلیل صوتی")
            yield AgentEvent(
                type="error",
                data={
                    "text": f"مرحله «{label}» نتوانست عملیات را کامل کند.",
                    "execution_id": context.execution_id,
                    "error_code": "audio_core_capability_failed",
                    "stage": label,
                    "capability": capability or "",
                    "cause_type": exc.cause_type or type(exc).__name__,
                    "detail": exc.detail,
                    "hint": _error_hint(capability),
                },
            )
            return

        if context.is_cancelled():
            yield AgentEvent(
                type="cancelled",
                data={
                    "text": "تحلیل صوتی متوقف شد.",
                    "execution_id": context.execution_id,
                },
            )
            return

        report = self._build_downloadable_report(result, context)
        if report is not None:
            report_url, filename, file_format = self._save_report(
                report["content"],
                filename=report["filename"],
                artifact_store=artifact_store,
            )
            if report_url:
                yield AgentEvent(
                    type="artifact",
                    data={
                        "type": "file",
                        "title": filename,
                        "url": report_url,
                        "agent_id": context.agent_id,
                        "meta": {
                            "operation": result.get("operation"),
                            "asset_id": result.get("asset_id"),
                            "format": file_format,
                        },
                    },
                )

        answer = result.get("answer")
        batch_results = result.get("batch_results")
        source_rows = []
        if isinstance(batch_results, list):
            for batch_item in batch_results:
                item_result = batch_item.get("result") or {}
                item_answer = item_result.get("answer")
                citations = (
                    item_answer.get("citations") or []
                    if isinstance(item_answer, dict)
                    else []
                )
                for item in citations:
                    if isinstance(item, dict):
                        source_rows.append(
                            {
                                "filename": batch_item.get("filename"),
                                "evidence_id": item.get("evidence_id"),
                                "asset_id": item.get("asset_id") or batch_item.get("asset_id"),
                                "start": (item.get("interval") or {}).get("start"),
                                "end": (item.get("interval") or {}).get("end"),
                                "text": item.get("excerpt"),
                            }
                        )
        elif isinstance(answer, dict):
            source_rows = [
                {
                    "evidence_id": item.get("evidence_id"),
                    "asset_id": item.get("asset_id"),
                    "start": (item.get("interval") or {}).get("start"),
                    "end": (item.get("interval") or {}).get("end"),
                    "text": item.get("excerpt"),
                }
                for item in (answer.get("citations") or [])
                if isinstance(item, dict)
            ]
        if source_rows:
            yield AgentEvent(
                type="sources",
                data={"execution_id": context.execution_id, "sources": source_rows},
            )

        done_data = {
            "execution_id": context.execution_id,
            "status": "completed",
            "operation": result.get("operation"),
            "asset_id": result.get("asset_id"),
        }
        if result.get("source_filename"):
            done_data["source_filename"] = str(result["source_filename"])
        if isinstance(batch_results, list):
            done_data["asset_ids"] = result.get("asset_ids") or []
            done_data["file_count"] = len(batch_results)
            done_data["text"] = self._batch_completion_text(result)
        elif isinstance(answer, dict) and answer.get("answer"):
            answer_text = str(answer["answer"])
            source_filename = str(result.get("source_filename") or "").strip()
            done_data["text"] = (
                f"فایل تحلیل‌شده: {source_filename}\n\n{answer_text}"
                if source_filename
                else answer_text
            )
            done_data["question"] = str(answer.get("question") or "")
            done_data["citations"] = answer.get("citations") or []
        elif result.get("transcript_text"):
            done_data["text"] = "تبدیل گفتار به متن با موفقیت انجام شد."
        elif result.get("summary"):
            done_data["text"] = "تحلیل صوتی با موفقیت انجام شد."
        else:
            done_data["text"] = "Audio analysis completed."

        yield AgentEvent(
            type="progress",
            data={
                "stage": "completed",
                "percent": 100,
                "text": "تحلیل صوتی با موفقیت انجام شد.",
                "execution_id": context.execution_id,
            },
        )
        yield AgentEvent(type="done", data=done_data)

    @staticmethod
    def _build_downloadable_report(
        result: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, str] | None:
        operation = result.get("operation")
        if isinstance(result.get("batch_results"), list):
            return {
                "content": AudioIntelligenceAgent._build_batch_markdown_report(result),
                "filename": f"audio_batch_{operation}_{context.execution_id}.md",
            }

        if operation == "summary":
            summary = result.get("summary")
            text = summary.get("summary") if isinstance(summary, dict) else None
            if isinstance(text, str) and text.strip():
                source_filename = str(result.get("source_filename") or "").strip()
                prefix = f"فایل صوتی: {source_filename}\n\n" if source_filename else ""
                return {
                    "content": prefix + text.strip() + "\n",
                    "filename": f"audio_summary_{context.execution_id}.txt",
                }

        if operation in {"ask", "evidence", "analyze"}:
            return {
                "content": AudioIntelligenceAgent._build_markdown_report(result),
                "filename": f"audio_{operation}_{context.execution_id}.md",
            }

        # Keep structured JSON internally useful for operations that do not
        # yet have a dedicated human-readable export contract.
        content = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        return {
            "content": content,
            "filename": f"audio_analysis_{context.execution_id}.json",
        }

    @staticmethod
    def _batch_completion_text(result: dict[str, Any]) -> str:
        items = result.get("batch_results") or []
        lines = [f"تحلیل {len(items)} فایل صوتی تکمیل شد."]
        for item in items:
            filename = str(item.get("filename") or "فایل صوتی")
            single = item.get("result") or {}
            answer = single.get("answer")
            summary = single.get("summary")
            if isinstance(answer, dict) and str(answer.get("answer") or "").strip():
                detail = str(answer["answer"]).strip()
            elif isinstance(summary, dict) and str(summary.get("summary") or "").strip():
                detail = str(summary["summary"]).strip()
            elif single.get("transcript_text"):
                detail = "رونویسی آماده است؛ متن کامل در گزارش پیوست قرار دارد."
            else:
                detail = "پردازش انجام شد؛ جزئیات در گزارش پیوست قرار دارد."
            if len(detail) > 1400:
                detail = detail[:1397].rstrip() + "..."
            lines.extend(["", f"**{filename}**", detail])
        return "\n".join(lines)

    @staticmethod
    def _build_batch_markdown_report(result: dict[str, Any]) -> str:
        operation = str(result.get("operation") or "analyze")
        items = result.get("batch_results") or []
        lines = [
            "# گزارش تجمیعی تحلیل صوتی",
            "",
            f"**عملیات:** {operation}",
            f"**تعداد فایل‌ها:** {len(items)}",
            "",
        ]
        for index, item in enumerate(items, start=1):
            filename = str(item.get("filename") or f"فایل {index}")
            single = item.get("result") or {}
            lines.extend(
                [
                    f"## {index}. {filename}",
                    "",
                    f"**شناسه فایل:** {item.get('asset_id') or single.get('asset_id') or '—'}",
                    "",
                ]
            )
            answer = single.get("answer")
            if isinstance(answer, dict):
                question = str(answer.get("question") or "").strip()
                answer_text = str(answer.get("answer") or "").strip()
                if question:
                    lines.extend(["### پرسش", "", question, ""])
                if answer_text:
                    lines.extend(["### پاسخ", "", answer_text, ""])
            summary = single.get("summary")
            if isinstance(summary, dict) and str(summary.get("summary") or "").strip():
                lines.extend(["### خلاصه", "", str(summary["summary"]).strip(), ""])
            transcript = str(single.get("transcript_text") or "").strip()
            if transcript:
                lines.extend(["### متن پیاده‌سازی‌شده", "", transcript, ""])
            for status_key, label, detail_key in (
                ("diarization_status", "تفکیک گویندگان", "diarization_diagnostic"),
                ("speaker_analysis_status", "تحلیل گویندگان", "speaker_analysis_diagnostic"),
                ("audio_events_status", "تشخیص رویدادهای صوتی", "audio_events_diagnostic"),
            ):
                if status_key in single:
                    status_value = str(single.get(status_key))
                    lines.extend([f"### وضعیت {label}", "", status_value, ""])
                    if single.get(detail_key):
                        lines.extend([str(single[detail_key])[:500], ""])
            evidence = single.get("evidence")
            if isinstance(evidence, dict) and evidence.get("spans"):
                lines.extend(["### شواهد زمانی", ""])
                for span in evidence.get("spans") or []:
                    interval = span.get("interval") or {}
                    excerpt = str(span.get("excerpt") or "").strip()
                    lines.append(
                        f"- {float(interval.get('start', 0) or 0):.2f} تا "
                        f"{float(interval.get('end', 0) or 0):.2f} ثانیه: {excerpt}"
                    )
                lines.append("")
            if not answer and not summary and not transcript and not evidence:
                lines.extend([
                    "جزئیات ساخت‌یافته:",
                    "",
                    chr(96) * 3 + "json",
                    json.dumps(single, ensure_ascii=False, indent=2, default=str),
                    chr(96) * 3,
                    "",
                ])
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _build_markdown_report(result: dict[str, Any]) -> str:
        lines = ["# گزارش تحلیل صوتی", ""]

        operation_labels = {
            "ask": "پرسش و پاسخ مستند",
            "evidence": "شواهد زمانی",
            "analyze": "تحلیل کامل صوت",
        }
        operation = str(result.get("operation") or "")
        lines.append(f"**عملیات:** {operation_labels.get(operation, operation)}")
        if result.get("source_filename"):
            lines.append(f"**نام فایل:** {result['source_filename']}")
        lines.append(f"**شناسه فایل:** `{result.get('asset_id', '—')}`")
        lines.append(f"**نوع رسانه:** `{result.get('media_type', '—')}`")
        lines.append("")

        answer = result.get("answer")
        if isinstance(answer, dict):
            question = str(answer.get("question") or "").strip()
            answer_text = str(answer.get("answer") or "").strip()
            if question:
                lines.extend(["## پرسش", "", question, ""])
            if answer_text:
                lines.extend(["## پاسخ", "", answer_text, ""])

        if result.get("transcript_text"):
            lines.extend(
                [
                    "## متن پیاده‌سازی‌شده",
                    "",
                    str(result["transcript_text"]).strip(),
                    "",
                ]
            )

        optional_stages = (
            ("diarization_status", "تفکیک گویندگان", "diarization_diagnostic"),
            ("speaker_analysis_status", "تحلیل گویندگان", "speaker_analysis_diagnostic"),
            ("audio_events_status", "تشخیص رویدادهای صوتی", "audio_events_diagnostic"),
        )
        visible_stages = [
            (label, result[status_key], result.get(detail_key))
            for status_key, label, detail_key in optional_stages
            if status_key in result
        ]
        if visible_stages:
            lines.extend(["## وضعیت قابلیت‌های تکمیلی", ""])
            status_labels = {
                "ok": "موفق",
                "unavailable": "در دسترس نیست",
                "skipped_diarization_unavailable": "رد شد؛ تفکیک گویندگان در دسترس نبود",
            }
            for label, status, diagnostic in visible_stages:
                lines.append(f"- **{label}:** {status_labels.get(status, status)}")
                if diagnostic:
                    lines.append(f"  - جزئیات: {str(diagnostic)[:500]}")
            lines.append("")

        evidence = result.get("evidence")
        if isinstance(evidence, dict):
            spans = evidence.get("spans") or []
            if spans:
                lines.extend(["## شواهد و استنادها", ""])
                for index, span in enumerate(spans, start=1):
                    interval = span.get("interval") or {}
                    start = float(interval.get("start", 0.0) or 0.0)
                    end = float(interval.get("end", 0.0) or 0.0)
                    excerpt = str(span.get("excerpt") or "").strip()
                    lines.append(f"### شواهد {index} — {start:.2f} تا {end:.2f} ثانیه")
                    lines.append("")
                    lines.append(f"> {excerpt}")
                    lines.append("")

        if isinstance(answer, dict) and answer.get("citations"):
            citation_spans = answer["citations"]
            lines.extend(["### استنادهای استفاده‌شده", ""])
            for index, citation in enumerate(citation_spans, start=1):
                interval = citation.get("interval") or {}
                start = float(interval.get("start", 0.0) or 0.0)
                end = float(interval.get("end", 0.0) or 0.0)
                excerpt = str(citation.get("excerpt") or "").strip()
                lines.append(
                    f"- **استناد {index}:** {start:.2f} تا {end:.2f} ثانیه — {excerpt}"
                )
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _save_report(
        content: str,
        *,
        filename: str,
        artifact_store: Any,
    ) -> tuple[str, str, str]:
        try:
            url = str(artifact_store.save(filename, content))
            file_format = filename.rsplit(".", 1)[-1].lower() if "." in filename else "file"
            return url, filename, file_format
        except Exception:
            return "", filename, "file"

    async def run(self, message: str, params: dict, session: Session) -> AsyncIterator[AgentEvent]:
        raise RuntimeError("AudioIntelligenceAgent requires Ai_cheshm AgentRuntime context")


__all__ = ["AudioIntelligenceAgent"]
