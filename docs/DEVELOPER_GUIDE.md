# Audio Intelligence Agent — Developer Guide

## Development order

1. Keep the platform contract stable.
2. Wire Core capability contracts.
3. Add provider adapters without leaking provider-native models.
4. Add reusable analysis/cache identity.
5. Add platform tests.
6. Run real E2E before integration.

## Cheshm contracts

- core/base_agent.py
- core/events.py
- core/platform/contracts.py
- core/platform/runtime.py
- core/platform/registry.py

## Media Core contracts

- src/media_intelligence/audio.py
- src/media_intelligence/transcription.py
- src/media_intelligence/language.py
- src/media_intelligence/diarization.py
- src/media_intelligence/speaker_analysis.py
- src/media_intelligence/transcript_search.py
- src/media_intelligence/topic_chapters.py
- src/media_intelligence/summarization.py
- src/media_intelligence/entities.py
- src/media_intelligence/audio_events.py
- src/media_intelligence/audio_evidence.py
- src/media_intelligence/grounded_qa.py

## Rule

Do not solve platform problems inside the Agent. Do not solve shared Core problems inside the Agent.
