import pytest
import io
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.infrastructure.audio.local_audio_service import LocalAudioService


@pytest.fixture
def mock_whisper():
    with patch("src.infrastructure.audio.local_audio_service.WhisperModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        # Mock transcribe result
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], None)
        
        yield mock_model_class, mock_model


@pytest.fixture
def mock_kokoro():
    with patch("src.infrastructure.audio.local_audio_service.Kokoro") as mock_kokoro_class:
        mock_kokoro_inst = MagicMock()
        mock_kokoro_class.return_value = mock_kokoro_inst
        
        # mock create return: (samples, sample_rate)
        import numpy as np
        mock_kokoro_inst.create.return_value = (np.array([1, 2, 3], dtype=np.float32), 24000)
        
        yield mock_kokoro_class, mock_kokoro_inst


@pytest.mark.asyncio
async def test_transcribe_audio(mock_whisper):
    _, mock_model = mock_whisper
    service = LocalAudioService("base", Path("dummy.onnx"), Path("dummy.bin"), "ef_dora")
    
    audio_file = io.BytesIO(b"dummy")
    result = await service.transcribe_audio(audio_file)
    
    assert result == "Hello world"
    # Ensure transcribe was called with the file
    call_args = mock_model.transcribe.call_args
    assert call_args is not None
    assert call_args[0][0] == audio_file
    assert call_args[1].get("beam_size") == 5


@pytest.mark.asyncio
async def test_synthesize_speech(mock_kokoro):
    mock_kokoro_class, mock_kokoro_inst = mock_kokoro
    
    with patch("pathlib.Path.exists", return_value=True), patch("soundfile.write") as mock_sf_write:
        
        # mock sf.write to write fake wave data to the buffer
        def side_effect(buf, samples, sample_rate, format):
            buf.write(b"fake_wav_data")
            
        mock_sf_write.side_effect = side_effect
        
        service = LocalAudioService("base", Path("dummy.onnx"), Path("dummy.bin"), "ef_dora")
        result = await service.synthesize_speech("Test text")
        
    assert result == b"fake_wav_data"
    mock_kokoro_inst.create.assert_called_once_with("Test text", voice="ef_dora", speed=1.0, lang="es")
    mock_sf_write.assert_called_once()
