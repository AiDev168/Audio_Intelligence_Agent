# Audio Intelligence Agent — Ai_cheshm Integration Contract

## Host boundary

Ai_cheshm is the security and execution host.

The Agent consumes authenticated execution context, protected file access, platform settings, the Media Core capability service, artifact storage and cancellation.

The Agent must not recreate authentication, RBAC, session persistence, WebSocket transport or platform execution state.

## Manifest

Stable ID: audio_intelligence

Capabilities: chat, file, media, audio_intelligence

Required host capabilities: agent_file_access, artifact_store, media_intelligence_core

Resource profile: heavy_audio_gpu

Outputs: text, file

## Input contract

User-selected audio is represented by a protected /storage/... URL.

The Agent validates the URL, resolves it through context.capabilities[agent_file_access], creates a Core MediaAsset from the trusted path, and never exposes that path to the user.

## Media Core contract

The preferred Host service is context.capabilities[media_intelligence_core]. It may be a thin Host facade around a Core CapabilityContainer.

The Agent never imports provider implementations such as WhisperX, pyannote, Tesseract or a remote API client.

## Execution contract

Use BaseAgent.execute() -> on_start() -> run_with_context() -> on_finish().

ExecutionContext is the source of truth for execution ID, session ID, user ID, agent ID, capabilities and cancellation.

## Capability mapping

| User operation | Core capability |
|---|---|
| Transcription | transcription |
| Language identification | language-identification |
| Diarization | diarization |
| Speaker analysis | speaker-turn-analysis |
| Temporal search | temporal-transcript-search |
| Topics / chapters | topic-chapter |
| Summarization | summarization |
| Entities / keywords | entity-extraction |
| Audio events | audio-event |
| Evidence | audio-evidence |
| Grounded Q&A | grounded-qa |

Pure deterministic capabilities such as temporal search, speaker attribution and evidence preparation do not need a provider ID. Provider-backed capabilities obtain the provider through the injected Host/Core policy.

## Reuse and timeline

The Agent derives a stable asset_id from the Core MediaAsset and stores the normalized transcript in session state.

The cache is disabled when cache_enabled=false.

A compatible transcript is reconstructed from Core-neutral objects and reused for later questions instead of retranscribing the asset.

The Agent also builds a canonical MediaTimeline from normalized transcript, speaker-turn and audio-event items. The user-facing result exposes only a safe timeline summary.

## Events

The Agent may emit thinking, progress, sources, artifact, done, error and cancelled events.

No event may contain raw local paths, API keys, provider credentials, stack traces or hidden reasoning.

Unexpected implementation exceptions are allowed to reach the Host runtime so developer-only diagnostics can capture them without exposing them to ordinary users.

## Artifact contract

The Agent uses context.capabilities[artifact_store].save(...).

The current implementation emits a protected JSON analysis artifact per successful execution.

The Agent never creates its own download endpoint.

## Cancellation and resource safety

For a raw Media Core CapabilityContainer, the adapter bridges Host cancellation into a Core CancellationToken.

For a Host-owned Media Core facade, cancellation remains a Host responsibility and is passed through as host_context.

Long-running execution is bounded by Ai_cheshm AgentRuntime timeout/resource controls.

## Security and isolation

- only protected storage URLs are accepted;
- user/session state is not global;
- artifacts carry the current agent_id;
- Core provenance must not contain credentials;
- provider-specific diagnostics belong to developer-only Host channels;
- no cross-agent private imports are allowed.

## Acceptance gate

Before merging into either repository main, verify Manifest discovery, Host dependency resolution, protected file access, real Core capability execution, progress and terminal events, cancellation, repeated-question reuse, artifact protection, user isolation, developer diagnostic isolation and real browser/WebSocket E2E.