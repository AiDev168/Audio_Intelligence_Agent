# Audio Intelligence Agent

General-purpose audio understanding Agent for the Ai_cheshm ecosystem.

This repository is an independent user-facing Agent. Reusable audio/media capabilities come from Ai_Media_Intelligence_Core, while authentication, sessions, lifecycle, protected files, artifacts, settings and resource governance belong to Ai_cheshm.

## Status

Phase 2 — Core orchestration implementation is in progress on:

feature/audio-agent-plugin-foundation-v1

Implemented in this branch:
- Cheshm Manifest and lifecycle adapter
- protected /storage/... input resolution
- Media Core dependency injection
- provider-neutral capability gateway
- host-to-Core cancellation bridge for raw Core containers
- transcription with session-scoped asset cache
- language identification
- diarization and speaker analysis
- temporal transcript search
- topics/chapters
- summarization
- entity/keyword extraction
- audio event analysis
- evidence preparation
- grounded Q&A
- canonical timeline summary
- protected JSON analysis artifact
- standard progress/source/done/error/cancelled events
- contract/unit tests for the plugin boundary

Actual model/provider implementations remain in the shared Core/provider layer.

## Mission

Turn audio into a reusable, timestamped intelligence timeline and answer grounded questions about transcription, language, speakers, topics, events and evidence.

Supported user profiles: general, podcast, meeting, lecture, interview, call.

## Architecture

    Ai_cheshm
      |
      | AgentRuntime / security / files / artifacts / settings
      v
    Audio Intelligence Agent
      |
      | domain orchestration + reuse policy
      v
    Ai_Media_Intelligence_Core
      |
      +-- transcription
      +-- language identification
      +-- diarization
      +-- speaker analysis
      +-- temporal search
      +-- topics / chapters
      +-- summarization
      +-- entities
      +-- audio events
      +-- evidence
      +-- grounded Q&A
      |
      v
    Canonical Media Timeline + Provenance

## Non-negotiable boundaries

- The Agent never owns authentication or RBAC.
- The Agent never creates its own WebSocket server or execution state machine.
- User file input must be a protected /storage/... URL.
- Local paths are resolved only by the host agent_file_access service.
- Provider-native objects never cross the Core boundary.
- The Agent never imports another user-facing Agent.
- Long-running work remains cancellation-aware and resource-bounded.
- Artifacts are returned through the platform artifact contract.
- Repeated questions reuse compatible cached analysis instead of retranscribing the same asset.
- Developer diagnostics remain host-owned and must not be emitted as normal user events.

## Execution flow

    User request
        |
        v
    AgentRuntime
        |
        v
    AudioIntelligenceAgent.run_with_context()
        |
        +--> validate request/dependencies
        +--> resolve protected media
        +--> build MediaAsset
        +--> select minimum required Core capabilities
        +--> reuse compatible transcript cache
        +--> build timeline/evidence
        +--> persist protected analysis artifact
        +--> emit standard AgentEvents
        |
        v
      done

## Provider policy

The Agent does not hard-code WhisperX, pyannote, FFmpeg, an LLM or a specific remote service.

When Ai_cheshm injects a Media Core facade, the host owns provider routing. When a raw Core CapabilityContainer is used for local/integration execution, provider selection may be supplied through ExecutionContext metadata under media_intelligence_provider_policy.

## Inputs and outputs

Input parameters may include audio_file, operation and query.

Operations: transcribe, language, diarize, speaker_analysis, search, topics, summary, entities, audio_events, evidence, ask and analyze.

Outputs are standard text and protected file artifacts. Grounded answers may also emit a sources event.

## Independent trace before Host integration

Run the deterministic Agent-only trace before starting Ai_cheshm. It does not load a model, open a network connection, or start the panel; it verifies the Agent orchestration order first:

```powershell
python tools/trace_orchestration.py --operation summary
pytest -q tests/test_trace_orchestration.py
```

Expected summary order is: protected input resolution → media asset creation → transcription capability → summarization capability → timeline/result.

## Verification before integration

The release gate is not only unit tests. The branch must pass Ruff check/format, Core capability integration, cancellation/cleanup verification, repeated-question reuse, real Ai_cheshm E2E, user isolation and developer-diagnostics isolation.

No merge to main is part of this branch until those checks are completed and explicitly authorized.

## Related contracts

- Ai_cheshm/AGENT_PLUGIN_DEVELOPMENT_STANDARD.md
- Ai_Media_Intelligence_Core/docs/AGENT_IMPLEMENTATION_HANDOFF_V1.md