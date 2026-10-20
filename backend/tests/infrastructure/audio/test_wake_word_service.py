import pytest
from unittest.mock import patch, MagicMock
from src.infrastructure.audio.wake_word_service import WakeWordService
import json

@patch("src.infrastructure.audio.wake_word_service.Model")
@patch("src.infrastructure.audio.wake_word_service.KaldiRecognizer")
def test_wake_word_service_process_chunk(mock_kaldi, mock_model_class):
    mock_recognizer_instance = MagicMock()
    mock_recognizer_instance.AcceptWaveform.return_value = False
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "atenea"})
    mock_kaldi.return_value = mock_recognizer_instance
    
    service = WakeWordService()
    audio_chunk = b'\x00' * 4096
    detected = service.process_chunk(audio_chunk)
    
    assert bool(detected) is True
    assert detected.agent_role == "supervisor"
    assert detected.display_name == "Atenea"
    mock_kaldi.assert_called_once()
    mock_recognizer_instance.AcceptWaveform.assert_called_once()


@patch("src.infrastructure.audio.wake_word_service.Model")
@patch("src.infrastructure.audio.wake_word_service.KaldiRecognizer")
def test_wake_word_service_detects_sphinx(mock_kaldi, mock_model_class):
    mock_recognizer_instance = MagicMock()
    mock_recognizer_instance.AcceptWaveform.return_value = False
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "sphinx hola que tal"})
    mock_kaldi.return_value = mock_recognizer_instance
    
    service = WakeWordService()
    audio_chunk = b'\x00' * 4096
    detected = service.process_chunk(audio_chunk)
    
    assert bool(detected) is True
    assert detected.agent_role == "the_judge"
    assert detected.display_name == "Sphinx"


@patch("src.infrastructure.audio.wake_word_service.Model")
@patch("src.infrastructure.audio.wake_word_service.KaldiRecognizer")
def test_wake_word_service_detects_accent_variations_and_aliases(mock_kaldi, mock_model_class):
    mock_recognizer_instance = MagicMock()
    mock_recognizer_instance.AcceptWaveform.return_value = False
    mock_kaldi.return_value = mock_recognizer_instance
    
    service = WakeWordService()
    audio_chunk = b'\x00' * 4096

    # Test "icaro" (without accent) maps to Ícaro
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "oye icaro que opinas"})
    detected_icaro = service.process_chunk(audio_chunk)
    assert bool(detected_icaro) is True
    assert detected_icaro.agent_role == "innovator_architect"
    assert detected_icaro.display_name == "Ícaro"

    # Test "esfinge" (Spanish phonetic alias for Vosk small) maps to Sphinx
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "esfinge revisa este adr"})
    detected_esfinge = service.process_chunk(audio_chunk)
    assert bool(detected_esfinge) is True
    assert detected_esfinge.agent_role == "the_judge"
    assert detected_esfinge.display_name == "Sphinx"

    # Test "hefesto" maps to Hefesto
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "hefesto prepara el despliegue"})
    detected_hefesto = service.process_chunk(audio_chunk)
    assert bool(detected_hefesto) is True
    assert detected_hefesto.agent_role == "devops_secops"
    assert detected_hefesto.display_name == "Hefesto"

    # Test "Hestia" decoded by Vosk as "bestia" or "este a"
    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "hola bestia"})
    detected_hestia_bestia = service.process_chunk(audio_chunk)
    assert bool(detected_hestia_bestia) is True
    assert detected_hestia_bestia.agent_role == "senior_architect"
    assert detected_hestia_bestia.display_name == "Hestia"

    mock_recognizer_instance.PartialResult.return_value = json.dumps({"partial": "este a dime algo"})
    detected_hestia_este_a = service.process_chunk(audio_chunk)
    assert bool(detected_hestia_este_a) is True
    assert detected_hestia_este_a.agent_role == "senior_architect"
    assert detected_hestia_este_a.display_name == "Hestia"



def test_wake_word_service_dynamic_registry_loads_all_subagent_profiles():
    service = WakeWordService()
    # Check that triggers dynamically include all profiles from sub_agent_profiles.py
    triggers = service._build_agent_triggers()
    
    assert "atenea" in triggers
    assert "sphinx" in triggers
    assert "hefesto" in triggers
    assert "aracne" in triggers
    assert "metis" in triggers
    assert "hermes" in triggers
    assert "hestia" in triggers
    assert "icaro" in triggers


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
    
    assert bool(detected) is False
    assert detected.agent_role is None
    assert detected.display_name is None

