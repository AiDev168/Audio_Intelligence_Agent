from audio_intelligence_agent.agent import AudioIntelligenceAgent


def test_agent_entry_point_is_importable_without_host_runtime():
    assert AudioIntelligenceAgent.__name__ == "AudioIntelligenceAgent"
    assert AudioIntelligenceAgent.manifest is not None
