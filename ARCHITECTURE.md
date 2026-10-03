# Audio Intelligence Agent Architecture

## Product boundary

Audio Intelligence is the user-facing orchestration layer for audio understanding. It is not the model runtime and not the shared media infrastructure.

## Layers

### Platform — Ai_cheshm
Owns identity, authentication, authorization, session, execution lifecycle, events, cancellation, settings, artifacts and resource governance.

### Agent — this repository
Owns audio profiles, user-facing workflows, capability orchestration, result presentation, reports, artifact policy and cache/reuse policy.

### Core — Ai_Media_Intelligence_Core
Owns canonical media models, capability contracts, provider adapters, timeline, evidence, provenance and resource profiles.

## Canonical pipeline

    protected media
       -> MediaAsset
       -> probe/validation
       -> transcription
       -> language identification
       -> diarization
       -> speaker analysis
       -> topics/chapters
       -> summarization
       -> entities
       -> audio events
       -> MediaTimeline
       -> temporal search/evidence
       -> grounded Q&A

Not every request executes every stage. The Agent should select the minimum capability set needed and reuse compatible cached results.

## Profiles

Profiles are modes, not separate Agents:
- podcast
- meeting
- lecture
- interview
- call
- general audio

## Grounded answers

Separate retrieval, evidence selection, reasoning and response generation. Grounded results should reference stable evidence spans with asset and timestamp information.

## Provider policy

Supported modes:
- local
- remote
- local-first
- remote-first

No random fallback.

## Caching

A derived-result cache key includes asset identity, capability, provider, model/version, meaningful options and schema version. Filename alone is never a cache identity.

## Cancellation and cleanup

Long-running capability calls must observe ExecutionContext cancellation where supported. Temporary media and provider resources must be released deterministically.

## Future deployment

The browser-facing contract remains stable if implementation moves from in-process to subprocess, GPU worker, queue or remote service.
