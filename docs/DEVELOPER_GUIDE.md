# راهنمای توسعه‌دهنده — تحلیلگر هوشمند صوتی

## مرز مسئولیت‌ها

- Ai_cheshm: احراز هویت، فایل، نشست، Artifact، لغو عملیات و تنظیمات.
- Audio Agent: workflow و orchestration کاربر.
- Ai_Media_Intelligence_Core: قراردادهای provider-neutral و capabilityها.
- Host provider assembly: اتصال Providerهای واقعی به Core.

Agent نباید مستقیماً به WhisperX، pyannote یا یک API خاص وابسته شود.

## ماتریس Providerها

| Capability | Core contract | Provider مورد نیاز |
|---|---|---|
| transcription | `TranscriptionCapability` | WhisperX یا ASR ریموت |
| language-identification | `LanguageIdentificationCapability` | می‌تواند از transcription همان اجرا استخراج شود |
| diarization | `DiarizationCapability` | WhisperX/pyannote یا Provider تخصصی |
| speaker-turn-analysis | `SpeakerTurnAnalysisCapability` | بدون Provider؛ منطق زمانی Core |
| temporal-transcript-search | `TemporalTranscriptSearchCapability` | بدون Provider؛ منطق Core |
| topic-chapter | `TopicChapterCapability` | مدل زبانی |
| summarization | `SummarizationCapability` | مدل زبانی |
| entity-extraction | `EntityExtractionCapability` | مدل زبانی |
| audio-event | `AudioEventCapability` | مدل تشخیص رویداد صوتی |
| audio-evidence | `AudioEvidenceCapability` | بدون Provider؛ منطق Core |
| grounded-qa | `GroundedQACapability` | مدل زبانی |

## حداقل مسیر عملیاتی فعلی

```text
Protected audio
    ↓
MediaAsset
    ↓
WhisperX local
    ↓
TranscriptionResult
    ↓
SummarizationCapability
    ↓
OpenAI-compatible local/remote LLM
    ↓
SummarizationResult
    ↓
Host artifact
    ↓
TXT download
```

## تنظیمات Provider

برای ASR محلی:

- `transcription_provider_mode`
- `whisper_model`
- `whisper_model_path`
- `whisper_device`
- `whisper_compute_type`
- `whisper_batch_size`

برای ASR ریموت:

- `remote_transcription_base_url`
- `remote_transcription_api_key`
- `remote_transcription_model`

برای مدل زبانی محلی:

- `local_semantic_base_url`
- `local_semantic_model`

برای مدل زبانی ریموت:

- `remote_semantic_base_url`
- `remote_semantic_api_key`
- `remote_semantic_model`

برای diarization:

- `diarization_provider_mode`
- `diarization_hf_token`
- `diarization_model`

## API Key و Secret

API Key نباید در Manifest، provenance، AgentEvent یا log قرار گیرد.

Cheshm `api_key`, `token`, `secret` و فیلدهای مشابه را از تنظیمات به‌صورت رمزنگاری‌شده نگهداری می‌کند، مشروط به فعال بودن `AI_CHESHM_SECRET_KEY`.

## Cache

Cache transcription باید همچنان شامل asset identity، capability، provider و options باشد تا تغییر مدل یا Provider باعث reuse اشتباه نشود.

## Provider-native object boundary

هیچ‌یک از این‌ها نباید از Core خارج شوند:

- WhisperX pipeline object
- pyannote pipeline object
- OpenAI SDK response object
- raw HTTP response

خروجی عمومی فقط مدل‌های Core است.

## تست

تست‌های حداقلی:

- Manifest فارسی
- تنظیمات Provider
- path validation
- Provider policy
- WhisperX assembly بدون نیاز به import در زمان startup
- semantic provider assembly
- cancellation
- cache identity
- artifact TXT برای خلاصه
- اجرای واقعی فایل صوتی قبل از merge

