"""Platform-facing manifest definition for Audio Intelligence."""

AGENT_MANIFEST = {
    "id": "audio_intelligence",
    "name": "Audio Intelligence",
    "description": "Understand audio, speakers, topics, events and timestamped evidence.",
    "icon": "🎧",
    "color": "#2563eb",
    "version": "0.1.0",
    "tags": ["audio", "speech", "transcription", "diarization", "evidence"],
    "capabilities": ["chat", "file", "media", "audio_intelligence"],
    "requires": ["media_intelligence_core"],
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
            {"title": "Quick Start", "text": "Select an audio file, choose a profile and ask for transcription, analysis or grounded evidence."},
            {"title": "Supported Inputs", "text": "Use protected audio/media files supplied by Ai_cheshm."},
            {"title": "Main Capabilities", "text": "Transcription, language ID, diarization, speaker analysis, search, chapters, summaries, entities, audio events and evidence."},
            {"title": "Outputs", "text": "Text answers and protected downloadable analysis artifacts."},
        ],
    },
}
