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
    assert call_args[1].get("language") == "es"
    prompt = call_args[1].get("initial_prompt", "")
    assert "castellano" in prompt.lower() or "español" in prompt.lower()
    assert "backend" in prompt.lower()
    assert "docker" in prompt.lower()


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


@pytest.mark.asyncio
async def test_synthesize_speech_applies_phonetic_normalization(mock_kokoro):
    _, mock_kokoro_inst = mock_kokoro

    with patch("pathlib.Path.exists", return_value=True), patch("soundfile.write") as mock_sf_write:
        mock_sf_write.side_effect = lambda buf, samples, sample_rate, format: buf.write(b"wav")
        service = LocalAudioService("base", Path("dummy.onnx"), Path("dummy.bin"), "ef_dora")
        await service.synthesize_speech("## 1. Desplegamos en **Docker** con Hefesto")

    mock_kokoro_inst.create.assert_called_once()
    spoken_text = mock_kokoro_inst.create.call_args[0][0]
    assert "dóquer" in spoken_text
    assert "efésto" in spoken_text.lower()
    assert "##" not in spoken_text
    assert "**" not in spoken_text


@pytest.mark.asyncio
async def test_kokoro_omp_num_threads_applied(mock_kokoro, monkeypatch):
    mock_kokoro_class, _ = mock_kokoro
    monkeypatch.setenv("KOKORO_OMP_NUM_THREADS", "4")

    with patch("pathlib.Path.exists", return_value=True), \
         patch("onnxruntime.InferenceSession") as mock_session_class, \
         patch("soundfile.write"):
        mock_kokoro_class.from_session.return_value = MagicMock()
        service = LocalAudioService("base", Path("dummy.onnx"), Path("dummy.bin"), "ef_dora")
        _ = service._get_kokoro()

        mock_session_class.assert_called_once()
        _, kwargs = mock_session_class.call_args
        sess_opts = kwargs.get("sess_options")
        assert sess_opts is not None
        assert sess_opts.intra_op_num_threads == 4
        mock_kokoro_class.from_session.assert_called_once()


@pytest.mark.asyncio
async def test_kokoro_default_threads_when_env_unset(mock_kokoro, monkeypatch):
    mock_kokoro_class, _ = mock_kokoro
    monkeypatch.delenv("KOKORO_OMP_NUM_THREADS", raising=False)

    with patch("pathlib.Path.exists", return_value=True):
        service = LocalAudioService("base", Path("dummy.onnx"), Path("dummy.bin"), "ef_dora")
        _ = service._get_kokoro()

        mock_kokoro_class.assert_called_once_with("dummy.onnx", "dummy.bin")


def test_lazy_model_initialization_is_thread_safe(mock_whisper, mock_kokoro):
    import concurrent.futures
    import threading

    mock_whisper_class, _ = mock_whisper
    mock_kokoro_class, _ = mock_kokoro

    whisper_gate = threading.Barrier(4)
    kokoro_gate = threading.Barrier(4)

    with patch("pathlib.Path.exists", return_value=True):
        service = LocalAudioService("base", Path("dummy.onnx"), Path("dummy.bin"), "ef_dora")

        def _load_whisper(_i: int):
            whisper_gate.wait(timeout=2.0)
            return service._get_whisper_model()

        def _load_kokoro(_i: int):
            kokoro_gate.wait(timeout=2.0)
            return service._get_kokoro()

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            whisper_results = list(pool.map(_load_whisper, range(4)))
            kokoro_results = list(pool.map(_load_kokoro, range(4)))

    assert mock_whisper_class.call_count == 1
    assert mock_kokoro_class.call_count == 1
    assert len({id(obj) for obj in whisper_results}) == 1
    assert len({id(obj) for obj in kokoro_results}) == 1
