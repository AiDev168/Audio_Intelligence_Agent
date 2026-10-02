# Audio Intelligence Agent — Ai_cheshm Integration Contract

## Host boundary

Ai_cheshm is the host platform and security boundary.

The Agent consumes authenticated identity, execution/session context, protected platform file URLs, platform settings, capabilities, artifact storage and cancellation.

The Agent must not recreate authentication, RBAC, session persistence, WebSocket transport or platform execution state.

## Manifest

Stable ID: audio_intelligence

Suggested capabilities:
- chat
- file
- media
- audio_intelligence

Required capability:
- media_intelligence_core

Resource profile:
- heavy_audio_gpu

Outputs:
- text
- file

The Manifest guide must be useful to normal users. Developer details belong in repository documentation.

## File contract

Accepted platform input is a protected /storage/... URL. Resolve it through the host file-access boundary. Arbitrary local paths are invalid user input.

## Execution contract

Use BaseAgent.execute -> on_start -> run_with_context -> on_finish.

Use ExecutionContext for execution_id, session_id, user_id, agent_id, capabilities and cancellation.

Never create a second execution state machine.

## Events

Use AgentEvent for progress, thinking, token, artifact, sources, done, error and cancelled events as appropriate.

Never emit secrets, API keys, raw local paths or provider credentials. Technical diagnostics belong to the platform developer-only channel.

## Core capability mapping

| User capability | Core capability |
|---|---|
| transcription | TranscriptionCapability |
| language identification | LanguageIdentificationCapability |
| diarization | DiarizationCapability |
| speaker analysis | SpeakerTurnAnalysisCapability |
| temporal search | TemporalTranscriptSearchCapability |
| topics/chapters | TopicChapterCapability |
| summarization | SummarizationCapability |
| entities/keywords | EntityExtractionCapability |
| audio events | AudioEventCapability |
| timestamped evidence | AudioEvidenceCapability |
| grounded Q&A | GroundedQACapability |

Provider-native objects must be normalized into Core models before reaching Agent logic.

## Timeline rule

Construct or consume a canonical timeline once and reuse it. A question must not cause a fresh transcription when compatible analysis already exists.

Stable identities include asset_id, segment_id, speaker_id, event_id and evidence_id.

## Artifact rule

Return generated files through the host artifact mechanism. Possible artifacts include timestamped transcript, speaker transcript, chapter report, summary, evidence report and analysis JSON/Markdown.

Never serve a local artifact directory.

## Security

- enforce platform user isolation
- do not expose raw paths
- do not log secrets
- do not put credentials in provenance
- do not concatenate untrusted input into shell commands
- use safe executable argument arrays
- keep developer diagnostics inaccessible to ordinary users

## Heavy workload

The design must remain portable across in-process, subprocess, GPU worker, queue and remote service deployments. Every long-running operation needs timeout, cancellation, cleanup and bounded concurrency.

## Acceptance tests

Before integration:
- manifest discovery
- settings loading
- protected file resolution
- successful execution
- progress events
- done/error/cancelled events
- artifact protection
- user isolation
- repeated execution cleanup
- cancellation
- Core contract integration
- repeated-question reuse
- developer diagnostic isolation
- real platform E2E

## Cross-agent rule

The Agent must never depend on private modules from Subtitle, Video or Media Investigator Agents. All reusable media intelligence comes from Ai_Media_Intelligence_Core.
