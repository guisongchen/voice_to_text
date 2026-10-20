"""Tests for cloud ASR mode selection and the CloudASRClient adapter."""

from unittest.mock import patch


def test_asr_mode_defaults_to_asrcore():
    from voice_to_text.config import ASR_MODE
    assert ASR_MODE in ("asrcore", "cloud")  # env may override locally


def test_service_uses_cloud_client_in_cloud_mode():
    """VoiceToTextService must pick CloudASRClient when ASR_MODE=cloud."""
    import voice_to_text.service as svc

    try:
        orig_mode = svc.ASR_MODE
        svc.ASR_MODE = "cloud"
        with patch.object(svc, "AudioRecorder"), \
             patch.object(svc, "AudioOutputController"), \
             patch.object(svc, "ASRCoreClient") as mock_local, \
             patch.object(svc, "CloudASRClient") as mock_cloud:
            service = svc.VoiceToTextService()
    finally:
        svc.ASR_MODE = orig_mode

    mock_cloud.assert_called_once_with()
    mock_local.assert_not_called()
    assert service._asr_client is mock_cloud.return_value


def test_service_uses_asrcore_client_by_default():
    import voice_to_text.service as svc

    with patch.object(svc, "AudioRecorder"), \
         patch.object(svc, "AudioOutputController"), \
         patch.object(svc, "ASRCoreClient") as mock_local, \
         patch.object(svc, "CloudASRClient") as mock_cloud:
        service = svc.VoiceToTextService()

    mock_local.assert_called_once_with(auto_start=True)
    mock_cloud.assert_not_called()
    assert service._asr_client is mock_local.return_value


def test_cloud_client_adapter_delegates():
    """CloudASRClient wraps CloudTranscriber and adapts the interface."""
    with patch("voice_to_text.cloud_asr.CloudTranscriber") as mock_t:
        instance = mock_t.return_value
        instance.transcribe.return_value = {"text": "你好", "detected_language": "", "duration_seconds": None}

        from voice_to_text.cloud_asr import CloudASRClient
        client = CloudASRClient()
        result = client.transcribe("/tmp/a.wav", model_name="ignored-local-name")
        client.close()

    instance.load.assert_called_once_with()
    instance.transcribe.assert_called_once_with("/tmp/a.wav", language=None)
    instance.unload.assert_called_once_with()
    assert result["text"] == "你好"
