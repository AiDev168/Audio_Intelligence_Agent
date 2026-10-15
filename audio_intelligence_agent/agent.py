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
        "topic-chapter": ("تنظیمات مدل زبانی و دسترسی سرویس به /chat/completions را بررسی کنید."),
        "entity-extraction": ("تنظیمات مدل زبانی و پاسخ JSON سرویس را بررسی کنید."),
        "grounded-qa": (
            "تنظیمات مدل زبانی را بررسی کنید؛ Provider باید پاسخ JSON شامل "
            "answer و citations برگرداند."
        ),
        "diarization": ("توکن Hugging Face، دسترسی مدل pyannote و سازگاری device را بررسی کنید."),
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

    @staticmethod
    def _is_download_request(message: str, params: dict[str, Any]) -> bool:
        if params.get("download_report") is True:
            return True
        operation = str(params.get("operation") or "").strip().casefold()
        if operation in {"download", "download_report", "export_report"}:
            return True
        text = str(message or "").strip().casefold()
        return any(
            term in text
            for term in (
                "دانلود گزارش",
                "گزارش را دانلود",
                "گزارش رو دانلود",
                "دانلود خروجی",
                "خروجی را دانلود",
                "دانلود فایل تکست",
                "دانلود فایل متنی",
                "دانلود فایل متن",
                "فایل تکست را دانلود",
                "فایل متنی را دانلود",
                "دانلود متن",
                "download report",
                "download the report",
                "download text",
                "download txt",
                "export report",
            )
        )

    @staticmethod
    def _report_source_filenames(result: dict[str, Any]) -> list[str]:
        batch_results = result.get("batch_results")
        if isinstance(batch_results, list):
            return list(
                dict.fromkeys(
                    str(item.get("filename") or "").strip()
                    for item in batch_results
                    if str(item.get("filename") or "").strip()
                )
            )
        filename = str(result.get("source_filename") or "").strip()
        return [filename] if filename else []

    @staticmethod
    def _safe_report_source_stem(filename: str) -> str:
        value = str(filename or "").replace(chr(92), "/").rsplit("/", 1)[-1]
        stem = value.rsplit(".", 1)[0] if "." in value else value
        safe = "".join(
            character if character.isalnum() or character in "-_." else "_" for character in stem
        ).strip("._-")
        return safe[:48] or "audio"

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

        download_requested = self._is_download_request(str(message or ""), dict(params or {}))
        if (
            not download_requested
            and not str(message or "").strip()
            and not any(
                str(params.get(key) or "").strip() for key in ("operation", "query", "audio_file")
            )
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
        pending_report = (
            (getattr(session, "state", {}).get("audio_intelligence") or {}).get(
                "pending_download_report"
            )
            if download_requested
            else None
        )
        if download_requested and not isinstance(pending_report, dict):
            yield AgentEvent(
                type="error",
                data={
                    "text": (
                        "گزارشی برای دانلود در این نشست آماده نیست. ابتدا فایل صوتی را تحلیل کنید."
                    ),
                    "execution_id": context.execution_id,
                    "error_code": "audio_report_not_available",
                },
            )
            return

        required_capabilities = (
            (("artifact_store", artifact_store),)
            if download_requested
            else (
                ("agent_file_access", file_access),
                ("artifact_store", artifact_store),
                ("media_intelligence_core", media_core),
            )
        )
        missing = [name for name, value in required_capabilities if value is None]
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

        if download_requested:
            names = list(pending_report.get("source_filenames") or [])
            source_label = "، ".join(names[:3])
            if len(names) > 3:
                source_label += f" و {len(names) - 3} فایل دیگر"
            thinking_text = (
                f"در حال آماده‌سازی گزارش قابل دانلود برای «{source_label}»..."
                if source_label
                else "در حال آماده‌سازی گزارش قابل دانلود..."
            )
        else:
            thinking_text = "در حال آماده‌سازی تحلیل صوتی..."

        yield AgentEvent(
            type="thinking",
            data={
                "text": thinking_text,
                "execution_id": context.execution_id,
            },
        )

        try:
            if download_requested:
                names = list(pending_report.get("source_filenames") or [])
                source_label = "، ".join(names)
                report_url, filename, file_format = self._save_report(
                    str(pending_report.get("content") or ""),
                    filename=str(pending_report.get("filename") or ""),
                    artifact_store=artifact_store,
                )
                if not report_url:
                    yield AgentEvent(
                        type="error",
                        data={
                            "text": "ساخت فایل گزارش ناموفق بود؛ گزارش ذخیره نشد.",
                            "execution_id": context.execution_id,
                            "error_code": "audio_report_export_failed",
                        },
                    )
                    return

                yield AgentEvent(
                    type="artifact",
                    data={
                        "type": "file",
                        "title": filename,
                        "url": report_url,
                        "agent_id": context.agent_id,
                        "meta": {
                            "kind": "audio_report",
                            "operation": pending_report.get("operation"),
                            "asset_id": pending_report.get("asset_id"),
                            "format": file_format,
                            "source_filename": names[0] if len(names) == 1 else "",
                            "source_filenames": names,
                        },
                    },
                )
                completion_text = (
                    f"گزارش مربوط به «{source_label}» آماده دانلود است."
                    if source_label
                    else "گزارش صوتی آماده دانلود است."
                )
                yield AgentEvent(
                    type="progress",
                    data={
                        "stage": "completed",
                        "percent": 100,
                        "text": completion_text,
                        "execution_id": context.execution_id,
                    },
                )
                yield AgentEvent(
                    type="done",
                    data={
                        "execution_id": context.execution_id,
                        "status": "completed",
                        "operation": "download_report",
                        "source_filenames": names,
                        "text": completion_text,
                    },
                )
                return

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
                    "hint": ("فایل صوتی، دسترسی آن و operation/پارامترهای درخواست را بررسی کنید."),
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

        request_text = str(params.get("query") or message or "").strip()
        report = self._build_downloadable_report(
            result,
            context,
            request_text=request_text,
        )
        audio_state = session.state.setdefault("audio_intelligence", {})
        audio_state.pop("pending_download_report", None)
        source_filenames = self._report_source_filenames(result)
        pending_report = None
        if report is not None:
            source_parts = [self._safe_report_source_stem(name) for name in source_filenames]
            if len(source_parts) == 1:
                report_filename = f"{source_parts[0]}_{report['filename']}"
            elif len(source_parts) > 1:
                prefix = "_and_".join(source_parts[:2])
                if len(source_parts) > 2:
                    prefix += f"_plus_{len(source_parts) - 2}_files"
                report_filename = f"{prefix}_{report['filename']}"
            else:
                report_filename = report["filename"]

            pending_report = {
                "content": report["content"],
                "filename": report_filename,
                "operation": result.get("operation"),
                "asset_id": result.get("asset_id"),
                "source_filenames": source_filenames,
            }
            audio_state["pending_download_report"] = pending_report

        answer = result.get("answer")
        batch_results = result.get("batch_results")
        source_rows = []
        if isinstance(batch_results, list):
            for batch_item in batch_results:
                item_result = batch_item.get("result") or {}
                item_answer = item_result.get("answer")
                citations = (
                    item_answer.get("citations") or [] if isinstance(item_answer, dict) else []
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
        else:
            summary = result.get("summary")
            summary_text = (
                str(summary.get("summary") or "").strip()
                if isinstance(summary, dict)
                else str(summary or "").strip()
            )
            transcript_text = str(result.get("transcript_text") or "").strip()
            operation = str(result.get("operation") or "").strip().lower()
            if summary_text:
                done_data["text"] = summary_text
            elif transcript_text and operation == "transcribe":
                done_data["text"] = transcript_text
            elif transcript_text:
                done_data["text"] = (
                    "تحلیل انجام شد، اما متن خلاصه تولید نشد. متن پیاده‌سازی‌شده:\n\n"
                    + transcript_text
                )
            else:
                done_data["text"] = "تحلیل اجرا شد، اما متن قابل نمایش تولید نشد."
        else:
            done_data["text"] = "Audio analysis completed."

        if pending_report is not None:
            if len(source_filenames) == 1:
                download_hint = (
                    f"برای دریافت گزارش فایل «{source_filenames[0]}»، "
                    "پیام «دانلود گزارش» را ارسال کنید."
                )
            elif source_filenames:
                download_hint = (
                    f"برای دریافت گزارش {len(source_filenames)} فایل صوتی، "
                    "پیام «دانلود گزارش» را ارسال کنید."
                )
            else:
                download_hint = "برای دریافت گزارش قابل دانلود، پیام «دانلود گزارش» را ارسال کنید."
            done_data["download_hint"] = download_hint
            done_data["text"] = (
                f"{done_data.get('text', 'تحلیل صوتی انجام شد.')}\n\n{download_hint}"
            )

        yield AgentEvent(
            type="progress",
            data={
                "stage": "completed",
                "percent": 100,
                "text": (
                    "تحلیل صوتی با موفقیت انجام شد؛ برای دریافت فایل، درخواست دانلود گزارش بدهید."
                ),
                "execution_id": context.execution_id,
            },
        )
        yield AgentEvent(type="done", data=done_data)

    @staticmethod
    def _build_downloadable_report(
        result: dict[str, Any],
        context: ExecutionContext,
        *,
        request_text: str = "",
    ) -> dict[str, str] | None:
        """Build a plain-text export of generated text; never export or attach source audio."""
        operation = str(result.get("operation") or "analyze").strip().lower()
        operation_labels = {
            "transcribe": "تبدیل گفتار به متن",
            "language": "تشخیص زبان",
            "diarize": "تفکیک گویندگان",
            "speaker_analysis": "تحلیل گویندگان",
            "search": "جست‌وجو در متن صوت",
            "topics": "موضوعات و فصل‌ها",
            "summary": "خلاصه‌سازی",
            "entities": "استخراج موجودیت‌ها",
            "evidence": "شواهد زمانی",
            "ask": "پرسش و پاسخ مستند",
            "analyze": "تحلیل کامل صوت",
        }
        lines = ["نتیجه متنی تحلیل صوتی", ""]
        generated_output_found = False

        if request_text.strip():
            lines.extend(["درخواست کاربر:", request_text.strip(), ""])
        lines.extend([f"عملیات: {operation_labels.get(operation, operation)}", ""])

        def add_value(label: str, value: Any, depth: int = 0) -> None:
            """Render structured analysis values as readable text instead of JSON."""
            if value is None or value == "":
                return
            indent = "  " * depth
            labels = {
                "title": "عنوان",
                "summary": "خلاصه",
                "text": "متن",
                "description": "توضیح",
                "start": "شروع",
                "end": "پایان",
                "speaker": "گوینده",
                "speaker_id": "شناسه گوینده",
                "entity_type": "نوع موجودیت",
                "normalized_text": "متن استاندارد",
                "chapters": "فصل‌ها",
                "entities": "موجودیت‌ها",
                "language": "زبان",
                "primary": "نتیجه اصلی",
                "confidence": "اطمینان",
                "excerpt": "متن شاهد",
                "question": "پرسش",
                "answer": "پاسخ",
                "name": "نام",
                "event_type": "نوع رویداد",
                "status": "وضعیت",
                "interval": "بازه زمانی",
            }
            hidden_keys = {
                "asset_id",
                "segment_id",
                "evidence_id",
                "provenance",
                "provider_version",
                "model_version",
                "core_schema_version",
                "source_asset_id",
            }
            if isinstance(value, str):
                text = value.strip()
                if text:
                    lines.append(f"{indent}{label + ': ' if label else ''}{text}")
                return
            if isinstance(value, (int, float, bool)):
                lines.append(f"{indent}{label + ': ' if label else ''}{value}")
                return
            if isinstance(value, dict):
                if label:
                    lines.append(f"{indent}{label}:")
                for key, item_value in value.items():
                    if key in hidden_keys or item_value is None or item_value == "":
                        continue
                    child_label = labels.get(
                        str(key),
                        str(key).replace("_", " ").strip().capitalize(),
                    )
                    add_value(child_label, item_value, depth + (1 if label else 0))
                return
            if isinstance(value, (list, tuple)):
                if label:
                    lines.append(f"{indent}{label}:")
                for index, item_value in enumerate(value, start=1):
                    if isinstance(item_value, (dict, list, tuple)):
                        add_value(f"مورد {index}", item_value, depth + (1 if label else 0))
                    else:
                        add_value("", item_value, depth + (1 if label else 0))

        def add_single_result(item: dict[str, Any], filename: str = "") -> None:
            nonlocal generated_output_found
            source_filename = filename or str(item.get("source_filename") or "").strip()
            if source_filename:
                lines.extend([f"فایل مبدأ: {source_filename}", ""])

            answer = item.get("answer")
            if isinstance(answer, dict):
                question = str(answer.get("question") or "").strip()
                answer_text = str(answer.get("answer") or "").strip()
                if question:
                    lines.extend(["پرسش:", question, ""])
                if answer_text:
                    lines.extend(["پاسخ تولیدشده:", answer_text, ""])
                    generated_output_found = True
                citations = answer.get("citations") or []
                if citations:
                    lines.append("استنادها:")
                    for index, citation in enumerate(citations, start=1):
                        if not isinstance(citation, dict):
                            continue
                        interval = citation.get("interval") or {}
                        start_time = interval.get("start")
                        end_time = interval.get("end")
                        excerpt = str(citation.get("excerpt") or "").strip()
                        timing = (
                            f"{float(start_time):.2f} تا {float(end_time):.2f} ثانیه"
                            if start_time is not None and end_time is not None
                            else "زمان نامشخص"
                        )
                        if excerpt:
                            lines.append(f"{index}. {timing}: {excerpt}")
                            generated_output_found = True
                    lines.append("")

            summary = item.get("summary")
            summary_text = summary.get("summary") if isinstance(summary, dict) else summary
            if isinstance(summary_text, str) and summary_text.strip():
                lines.extend(["خلاصه تولیدشده:", summary_text.strip(), ""])
                generated_output_found = True

            transcript_text = str(item.get("transcript_text") or "").strip()
            if transcript_text and operation in {"transcribe", "analyze"}:
                lines.extend(["متن پیاده‌سازی‌شده:", transcript_text, ""])
                generated_output_found = True

            structured_sections = (
                ("language", "نتیجه تشخیص زبان"),
                ("topics", "موضوعات و فصل‌ها"),
                ("entities", "موجودیت‌های استخراج‌شده"),
                ("search", "نتیجه جست‌وجو"),
                ("diarization", "نتیجه تفکیک گویندگان"),
                ("speaker_analysis", "تحلیل گویندگان"),
                ("audio_events", "رویدادهای صوتی"),
                ("evidence", "شواهد زمانی"),
            )
            for key, label in structured_sections:
                value = item.get(key)
                if not value:
                    continue
                if key == "evidence" and isinstance(value, dict) and value.get("spans"):
                    lines.append("شواهد زمانی:")
                    for index, span in enumerate(value.get("spans") or [], start=1):
                        if not isinstance(span, dict):
                            continue
                        interval = span.get("interval") or {}
                        start_time = interval.get("start")
                        end_time = interval.get("end")
                        excerpt = str(span.get("excerpt") or "").strip()
                        timing = (
                            f"{float(start_time):.2f} تا {float(end_time):.2f} ثانیه"
                            if start_time is not None and end_time is not None
                            else "زمان نامشخص"
                        )
                        if excerpt:
                            lines.append(f"{index}. {timing}: {excerpt}")
                            generated_output_found = True
                    lines.append("")
                else:
                    lines.append(f"{label}:")
                    add_value("", value, 1)
                    lines.append("")
                    generated_output_found = True

        batch_results = result.get("batch_results")
        if isinstance(batch_results, list):
            for index, batch_item in enumerate(batch_results, start=1):
                item_result = batch_item.get("result") or {}
                filename = str(batch_item.get("filename") or f"فایل {index}")
                if index > 1:
                    lines.extend(["", "----------------------------------------", ""])
                add_single_result(item_result, filename)
        else:
            add_single_result(result)

        if not generated_output_found:
            return None
        content = "\n".join(lines).rstrip() + "\n"
        return {
            "content": content,
            "filename": f"audio_result_{operation}_{context.execution_id}.txt",
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
                lines.extend(
                    [
                        "جزئیات ساخت‌یافته:",
                        "",
                        chr(96) * 3 + "json",
                        json.dumps(single, ensure_ascii=False, indent=2, default=str),
                        chr(96) * 3,
                        "",
                    ]
                )
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
                lines.append(f"- **استناد {index}:** {start:.2f} تا {end:.2f} ثانیه — {excerpt}")
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
