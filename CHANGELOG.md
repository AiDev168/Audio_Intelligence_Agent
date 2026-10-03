# Changelog

## Unreleased

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
