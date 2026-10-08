import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from unittest.mock import patch

app = create_app()
client = TestClient(app)

@patch("src.presentation.api.ws.wake_word.wake_word_service.process_chunk")
def test_wake_word_websocket_detected(mock_process_chunk):
    # Setup mock to return True (Wake word detected)
    mock_process_chunk.return_value = True
    
    with client.websocket_connect("/ws/audio/wake-word") as websocket:
        # Send fake audio chunk
        websocket.send_bytes(b'\x00' * 1024)
        
        # Expect the server to send WAKE_WORD_DETECTED
        response = websocket.receive_json()
        assert response["type"] == "WAKE_WORD_DETECTED"
        
        mock_process_chunk.assert_called_once()

import time

@patch("src.presentation.api.ws.wake_word.wake_word_service.process_chunk")
def test_wake_word_websocket_not_detected(mock_process_chunk):
    # Setup mock to return False
    mock_process_chunk.return_value = False
    
    with client.websocket_connect("/ws/audio/wake-word") as websocket:
        # Send fake audio chunk
        websocket.send_bytes(b'\x00' * 1024)
        
        # We don't expect any message back, but we need to wait for event loop to process
        time.sleep(0.1)
        mock_process_chunk.assert_called_once()
