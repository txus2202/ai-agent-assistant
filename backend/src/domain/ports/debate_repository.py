from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.value_objects.debate_record import DebateRecord

class IDebateRepository(ABC):
    @abstractmethod
    def create(self, debate: DebateRecord) -> None:
        """Saves a new debate record."""

    @abstractmethod
    def append_event(self, debate_id: str, event_json: str) -> None:
        """Appends a single event to a debate's event log."""

    @abstractmethod
    def update_status(self, debate_id: str, status: str) -> None:
        """Updates the status of a debate."""

    @abstractmethod
    def update_session(self, debate_id: str, status: str, target_agent: Optional[str] = None) -> None:
        """Updates status and target agent for an existing continuous debate session."""


    @abstractmethod
    def find_all(self) -> List[DebateRecord]:
        """Returns all debates."""

    @abstractmethod
    def find_by_id(self, debate_id: str) -> Optional[DebateRecord]:
        """Finds a debate by ID."""

    @abstractmethod
    def delete(self, debate_id: str) -> None:
        """Deletes a debate by ID."""
