# Changelog

## Unreleased

## Completed integration updates

- Grounded Q&A citations are normalized to the exact Core evidence IDs before Core validation.
- User-facing `ask`, `evidence` and `analyze` results are exported as readable Markdown instead of raw JSON.
- `ask` answers are surfaced directly through the standard Host `done` event.
- The local faster-whisper path remains VAD-free and automatically splits long decoded audio into bounded clips for batched inference.
- Audio answer display in Cheshm intentionally shows the final answer text in the central chat rather than rendering evidence chunks as separate answer cards.


### Added
- Cheshm-compatible Audio Intelligence plugin foundation.
- Complete Manifest parameter and settings contract.
- Media Core capability gateway with dependency injection.
- Host cancellation bridge for raw Media Core execution.
- Audio-domain orchestration for the documented capability set.
- Session-scoped transcription reuse keyed by Core asset identity.
- Canonical timeline construction and safe timeline summary.
- Protected JSON analysis artifact output.
- Standard thinking, progress, sources, done, error and cancelled events.
- Plugin boundary and orchestration contract tests.

### Verification still required
- real Media Core provider execution;
- real Ai_cheshm Host registration and WebSocket execution;
- cancellation under a real long-running provider;
- artifact and user-isolation E2E;
- final CI green status on the completed branch;
- merge authorization from the repository owner.

### Updated
- Persian-first user guide with capability descriptions and setting explanations.
- Explicit remote provider fields: Base URL, API Key and Model.
- Whisper model path made the primary local-model setting; model name documented as optional.
- Provider priority wording clarified so local-first/remote-first is not presented as runtime failover.
- Downloadable TXT summary workflow documented.

## Diagnostics

- Core execution failures now preserve capability, exception type and safe diagnostic detail.
- Caught Core failures are logged with execution IDs and traceback information.
- Structured error events include actionable stage/hint metadata for the Host UI.


## Fast transcript workflow

- Standard transcription is now designed to be provider-optimized at the Host boundary.
- Summary, topics, entities, search and grounded QA consume canonical transcription and do not inherently require diarization.
- Basic Q&A/evidence no longer forces the audio-event capability.
- Heavy speaker/diarization capabilities remain separate and may use WhisperX/Pyannote.
