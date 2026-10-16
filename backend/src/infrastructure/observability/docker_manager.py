"""
Infrastructure: DockerObservabilityManager
Controls the local Langfuse Docker Compose stack based on system configuration.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class DockerObservabilityManager:
    """Manages the lifecycle of the Langfuse Docker stack."""

    def __init__(self, compose_file: Path | None = None) -> None:
        if compose_file is not None:
            self.compose_file = compose_file
        else:
            # Locate docker-compose.yml relative to project root
            base_dir = Path(__file__).resolve().parents[4]
            candidate = base_dir / "docker-compose.yml"
            self.compose_file = candidate if candidate.exists() else Path("docker-compose.yml")

    def is_docker_available(self) -> bool:
        """Check if docker CLI is installed and available in PATH."""
        return shutil.which("docker") is not None

    def is_stack_running(self) -> bool:
        """Check if any containers of the docker-compose stack are currently running."""
        if not self.is_docker_available() or not self.compose_file.exists():
            return False
        try:
            cmd = ["docker", "compose", "-f", str(self.compose_file), "ps", "--status", "running", "-q"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
            return bool(res.stdout and res.stdout.strip())
        except Exception as exc:
            logger.debug("Failed to check docker stack running status: %s", exc)
            return False

    def start_stack(self) -> bool:
        """Start the Langfuse stack via `docker compose up -d` if not already running."""
        if not self.is_docker_available():
            logger.warning("Docker CLI is not found on PATH. Cannot start Langfuse stack.")
            return False
        if not self.compose_file.exists():
            logger.warning("docker-compose.yml not found at %s. Cannot start Langfuse stack.", self.compose_file)
            return False

        if self.is_stack_running():
            logger.info("Langfuse Docker stack is already active.")
            return True

        try:
            logger.info("Starting Langfuse Docker stack via docker compose up -d...")
            cmd = ["docker", "compose", "-f", str(self.compose_file), "up", "-d"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if res.returncode == 0:
                logger.info("Langfuse Docker stack started successfully.")
                return True
            else:
                logger.warning("docker compose up -d exited with code %s: %s", res.returncode, res.stderr)
                return False
        except Exception as exc:
            logger.warning("Error starting Langfuse Docker stack: %s", exc)
            return False

    def stop_stack(self) -> bool:
        """Stop the Langfuse stack via `docker compose stop` if running."""
        if not self.is_docker_available() or not self.compose_file.exists():
            return False

        if not self.is_stack_running():
            return True

        try:
            logger.info("Stopping Langfuse Docker stack via docker compose stop...")
            cmd = ["docker", "compose", "-f", str(self.compose_file), "stop"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            if res.returncode == 0:
                logger.info("Langfuse Docker stack stopped successfully.")
                return True
            else:
                logger.warning("docker compose stop exited with code %s: %s", res.returncode, res.stderr)
                return False
        except Exception as exc:
            logger.warning("Error stopping Langfuse Docker stack: %s", exc)
            return False

    def ensure_stack_state(self, enabled: bool) -> bool:
        """Ensure the Docker stack matches the desired state."""
        # Avoid running real Docker commands in pytest
        if "pytest" in sys.modules or os.environ.get("ENV") == "test":
            logger.debug("Test environment detected; skipping Docker stack control.")
            return True

        if enabled:
            return self.start_stack()
        else:
            return self.stop_stack()
