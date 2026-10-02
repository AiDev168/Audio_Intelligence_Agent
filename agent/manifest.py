"""Platform-facing manifest definition for Audio Intelligence."""

AGENT_MANIFEST = {
    "id": "audio_intelligence",
    "name": "Audio Intelligence",
    "description": "Understand audio, speakers, topics, events and timestamped evidence.",
    "icon": "🎧",
    "color": "#2563eb",
    "version": "0.2.0",
    "tags": ["audio", "speech", "transcription", "diarization", "evidence"],
    "capabilities": ["chat", "file", "media", "audio_intelligence"],
    "params": {
        "type": "object",
        "properties": {
            "audio_file": {
                "type": "string",
                "format": "file",
                "accept": "audio/*",
                "title": "Audio file",
                "description": "Select an audio file uploaded to Ai_cheshm.",
            },
            "operation": {
                "type": "string",
                "default": "",
                "enum": [
                    "transcribe",
                    "language",
                    "diarize",
                    "speaker_analysis",
                    "search",
                    "topics",
                    "summary",
                    "entities",
                    "audio_events",
                    "evidence",
                    "ask",
                    "analyze",
                ],
            },
            "query": {
                "type": "string",
                "default": "",
                "title": "Question or search text",
            },
        },
    },
    "requires": ["agent_file_access", "artifact_store", "media_intelligence_core"],
    "resource_profile": "heavy_audio_gpu",
    "output_types": ["text", "file"],
    "settings": {
        "properties": {
            "profile": {
                "type": "string",
                "default": "general",
                "enum": ["general", "podcast", "meeting", "lecture", "interview", "call"],
            },
            "execution_policy": {
                "type": "string",
                "default": "local-first",
                "enum": ["local", "remote", "local-first", "remote-first"],
            },
            "cache_enabled": {"type": "boolean", "default": True},
            "evidence_limit": {"type": "integer", "default": 20},
        }
    },
    "guide": {
        "title": "Audio Intelligence",
        "summary": "Analyze audio, speakers, topics and timestamped evidence.",
        "sections": [
            {
                "title": "Quick Start",
                "text": (
                    "Upload an audio file, choose an optional operation, then ask for "
                    "transcription, analysis, search, summary or grounded evidence."
                ),
            },
            {
                "title": "Supported Inputs",
                "text": "Use protected audio/media files supplied by Ai_cheshm.",
            },
            {
                "title": "Main Capabilities",
                "text": (
                    "Transcription, language ID, diarization, speaker analysis, search, "
                    "chapters, summaries, entities, audio events and timestamped Q&A."
                ),
            },
            {
                "title": "Outputs",
                "text": "Text answers, timestamped evidence and protected analysis files.",
            },
            {
                "title": "Resource Expectations",
                "text": (
                    "Audio analysis may use CPU/GPU workers. Long operations support "
                    "platform timeout and cancellation."
                ),
            },
        ],
    },
}
