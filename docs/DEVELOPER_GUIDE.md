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
| transcription | `TranscriptionCapability` | faster-whisper local یا ASR ریموت |
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
faster-whisper local
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



## Long-audio local ASR contract

The normal local transcription path intentionally keeps `vad_filter=False`. For audio longer than the model chunk length, the Host decodes the real waveform duration and supplies bounded clip ranges (for example 0–30s, 30–45s) to `BatchedInferencePipeline`. This avoids the 30-second single-clip limitation while preserving the no-WhisperX-VAD contract.

## User-facing answer contract

The Agent emits the final grounded answer through the standard `done` event. The Host renders the answer text in the main chat. Source/citation metadata remains available to the platform but is not rendered as a list of transcript chunks in the central answer view.


## Multi-file input, stale-result avoidance, and cache identity

The service resolves explicit form URLs first, then selected session document IDs. If selection is absent and several audio files exist, it fails with a Persian prompt rather than selecting the last active audio. Multiple files are analyzed sequentially with independent per-file Core calls and an aggregate Markdown report. The transcription cache schema is versioned and the key includes SHA-256 of file content in addition to asset ID, provider policy, and transcription options. A malformed cache item is removed by its cache key, not by asset ID.


## Capability availability and partial full-analysis reports

The Core declares an audio-event capability, but the current Host assembly has no production audio-event provider. It is not advertised as an executable operation in the user-facing manifest. During a full analysis, diarization, speaker-turn attribution, and audio-event detection are treated as optional stages: provider/model failures are captured as status+safe diagnostic fields so transcription, language identification, topics, summary and entity extraction can continue when their required providers work. Direct requests to a capability that has no provider still fail explicitly.
