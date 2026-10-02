# Audio Intelligence Agent

General-purpose audio understanding Agent for the Ai_cheshm ecosystem.

This repository is an independent user-facing Agent. It is not a second media-processing framework: reusable audio/media capabilities come from Ai_Media_Intelligence_Core, while authentication, sessions, lifecycle, protected files, artifacts, settings and resource governance belong to Ai_cheshm.

## Status

Phase 1 — Plugin foundation / contract implementation

First implementation branch: feature/audio-agent-plugin-foundation-v1.

## Mission

Turn audio into a reusable, timestamped intelligence timeline and answer grounded questions about:

1. transcription
2. language identification
3. speaker diarization
4. speaker/turn analysis
5. temporal transcript search
6. topic/chapter extraction
7. summarization
8. keyword/entity extraction
9. audio-event analysis
10. timestamped Q&A/evidence

Supported profiles include podcast, meeting, lecture, interview, call/voice recording and general audio.

## Architecture

    Ai_cheshm
      |
      | AgentRuntime / security / files / artifacts / settings
      v
    Audio Intelligence Agent
      |
      | domain orchestration
      v
    Ai_Media_Intelligence_Core
      |
      +-- transcription
      +-- language identification
      +-- diarization
      +-- speaker analysis
      +-- transcript search
      +-- topics/chapters
      +-- summarization
      +-- entities
      +-- audio events
      +-- evidence / grounded QA
      |
      v
    Canonical Media Timeline + Provenance

## Non-negotiable boundaries

- The Agent never owns authentication or RBAC.
- The Agent never creates its own WebSocket server.
- The Agent never exposes local filesystem paths to the browser.
- The Agent never imports another user-facing Agent.
- Provider-native objects never cross the Core boundary.
- Long-running work must remain cancellation-aware and resource-bounded.
- Artifacts are returned through the platform artifact contract.
- Repeated questions must reuse derived analysis instead of retranscribing media.

## Repository contract

Planned structure:

    agent/
      __init__.py
      agent.py
    tests/
      unit/
      integration/
      platform/
      e2e/
    docs/
      USER_GUIDE.md
      DEVELOPER_GUIDE.md
    AGENT_INTEGRATION.md
    ARCHITECTURE.md
    CHANGELOG.md

## Current integration target

The Agent subclasses core.base_agent.BaseAgent and exposes a Manifest with a stable ID, user guide, audio capabilities, Core dependency, heavy-audio resource profile and text/file outputs.

Platform lifecycle:

    BaseAgent.execute()
      -> refresh settings
      -> on_start()
      -> run_with_context()
      -> on_finish()

## Core dependency direction

    Ai_cheshm
       |
    Audio Intelligence Agent
       |
    Ai_Media_Intelligence_Core
       |
    Providers / deployment policy

Never create private dependencies on Subtitle, Video or Media Investigator Agents.

## Development principles

- Provider selection is explicit: local, remote, local-first or remote-first.
- Cache keys include asset identity, capability, provider/model/version and meaningful options.
- Provenance is retained for derived results.
- Technical diagnostics are developer-only.
- Temporary media work is cleaned up deterministically.
- Unit tests are not sufficient; Core/platform integration and a real E2E path are required before integration.

## Roadmap

### Phase 1
- plugin skeleton
- Manifest
- platform lifecycle adapter
- Core capability wiring
- settings schema
- safe media input handling
- progress/error/artifact events
- unit/platform contract tests

### Phase 2
- real transcription provider
- language identification
- diarization and speaker analysis
- reusable timeline/cache

### Phase 3
- temporal search
- topics/chapters
- summarization
- entities
- audio events
- grounded evidence/Q&A

### Phase 4
- real Ai_cheshm E2E integration
- resource stress tests
- cancellation/cleanup verification
- user isolation verification
- developer diagnostics verification

## Related contracts

- Ai_cheshm/AGENT_PLUGIN_DEVELOPMENT_STANDARD.md
- Ai_Media_Intelligence_Core/docs/AGENT_IMPLEMENTATION_HANDOFF_V1.md
