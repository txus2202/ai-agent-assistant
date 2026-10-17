"""
Unit tests for DockerObservabilityManager.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.infrastructure.observability.docker_manager import DockerObservabilityManager


def test_is_docker_available_uses_shutil_which():
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/local/bin/docker"
        mgr = DockerObservabilityManager()
        assert mgr.is_docker_available() is True

        mock_which.return_value = None
        assert mgr.is_docker_available() is False


def test_is_stack_running_checks_compose_ps(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    mgr = DockerObservabilityManager(compose_file=compose_file)

    with patch.object(mgr, "is_docker_available", return_value=True), \
         patch("subprocess.run") as mock_run:
        # Stack running
        mock_run.return_value = MagicMock(returncode=0, stdout="c1\nc2\n")
        assert mgr.is_stack_running() is True

        # Stack not running
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert mgr.is_stack_running() is False


def test_start_stack_when_already_running(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    mgr = DockerObservabilityManager(compose_file=compose_file)

    with patch.object(mgr, "is_docker_available", return_value=True), \
         patch.object(mgr, "is_stack_running", return_value=True), \
         patch("subprocess.run") as mock_run:
        res = mgr.start_stack()
        assert res is True
        mock_run.assert_not_called()


def test_start_stack_when_not_running(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    mgr = DockerObservabilityManager(compose_file=compose_file)

    with patch.object(mgr, "is_docker_available", return_value=True), \
         patch.object(mgr, "is_stack_running", return_value=False), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Started")
        res = mgr.start_stack()
        assert res is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "up" in cmd
        assert "-d" in cmd


def test_stop_stack_when_running(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    mgr = DockerObservabilityManager(compose_file=compose_file)

    with patch.object(mgr, "is_docker_available", return_value=True), \
         patch.object(mgr, "is_stack_running", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Stopped")
        res = mgr.stop_stack()
        assert res is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "stop" in cmd


def test_stop_stack_when_not_running(tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    mgr = DockerObservabilityManager(compose_file=compose_file)

    with patch.object(mgr, "is_docker_available", return_value=True), \
         patch.object(mgr, "is_stack_running", return_value=False), \
         patch("subprocess.run") as mock_run:
        res = mgr.stop_stack()
        assert res is True
        mock_run.assert_not_called()
