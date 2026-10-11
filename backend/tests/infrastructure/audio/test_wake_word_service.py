import pytest
from unittest.mock import patch, MagicMock
from src.infrastructure.audio.wake_word_service import WakeWordService
import json

@patch("src.infrastructure.audio.wake_word_service.Model")
@patch("src.infrastructure.audio.wake_word_service.KaldiRecognizer")
def test_wake_word_service_process_chunk(mock_kaldi, mock_model_class):
    # Setup mock Recognizer
    mock_recognizer_instance = MagicMock()
    # Simulate Vosk returning a partial result with 'atenea'
    mock_recognizer_instance.AcceptWaveform.return_value = False
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "atenea"})
    mock_kaldi.return_value = mock_recognizer_instance
    
    # Initialize service
    service = WakeWordService()
    
    # Call process_chunk with a zero-filled byte array
    audio_chunk = b'\x00' * 4096
    detected = service.process_chunk(audio_chunk)
    
    assert detected is True
    mock_kaldi.assert_called_once()
    mock_recognizer_instance.AcceptWaveform.assert_called_once()

@patch("src.infrastructure.audio.wake_word_service.Model")
@patch("src.infrastructure.audio.wake_word_service.KaldiRecognizer")
def test_wake_word_service_no_detection(mock_kaldi, mock_model_class):
    mock_recognizer_instance = MagicMock()
    mock_recognizer_instance.AcceptWaveform.return_value = False
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "nada"})
    mock_kaldi.return_value = mock_recognizer_instance
    
    service = WakeWordService()
    
    audio_chunk = b'\x00' * 4096
    detected = service.process_chunk(audio_chunk)
    
    assert detected is False
