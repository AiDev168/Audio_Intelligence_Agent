from audio_intelligence_agent.manifest import AGENT_MANIFEST


def test_manifest_has_required_plugin_contract():
    required = {
        "id",
        "name",
        "description",
        "version",
        "capabilities",
        "params",
        "requires",
        "resource_profile",
        "output_types",
        "guide",
        "settings",
    }
    assert required <= AGENT_MANIFEST.keys()
    assert AGENT_MANIFEST["id"] == "audio_intelligence"
    assert {
        "agent_file_access",
        "artifact_store",
        "media_intelligence_core",
    } <= set(AGENT_MANIFEST["requires"])
    assert AGENT_MANIFEST["resource_profile"] == "heavy_audio_gpu"
    assert "audio_file" in AGENT_MANIFEST["params"]["properties"]
    assert "operation" in AGENT_MANIFEST["params"]["properties"]


def test_manifest_does_not_expose_provider_specific_capabilities():
    capabilities = set(AGENT_MANIFEST["capabilities"])
    assert "whisperx" not in capabilities
    assert "pyannote" not in capabilities
    assert "ffmpeg" not in capabilities
