from agent.manifest import AGENT_MANIFEST


def test_manifest_has_required_plugin_contract():
    required = {
        "id", "name", "description", "version", "capabilities", "requires",
        "resource_profile", "output_types", "guide", "settings",
    }
    assert required <= AGENT_MANIFEST.keys()
    assert AGENT_MANIFEST["id"] == "audio_intelligence"
    assert "media_intelligence_core" in AGENT_MANIFEST["requires"]
    assert AGENT_MANIFEST["resource_profile"] == "heavy_audio_gpu"


def test_manifest_does_not_expose_provider_specific_capabilities():
    capabilities = set(AGENT_MANIFEST["capabilities"])
    assert "whisperx" not in capabilities
    assert "pyannote" not in capabilities
    assert "ffmpeg" not in capabilities
