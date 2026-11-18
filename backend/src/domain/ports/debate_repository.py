from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.value_objects.debate_record import DebateRecord, PaginatedDebateSummaries

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
    def find_all(self, user_id: Optional[str] = None, allow_unscoped: bool = False) -> List[DebateRecord]:
        """Returns all debates, optionally filtered by user_id. Fail-closed if user_id is None unless allow_unscoped=True."""

    @abstractmethod
    def find_paginated_summaries(
        self,
        user_id: Optional[str] = None,
        allow_unscoped: bool = False,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        filter_by: Optional[str] = None,
    ) -> PaginatedDebateSummaries:
        """Returns paginated lightweight debate summaries without serializing full event arrays."""

    @abstractmethod
    def find_by_id(self, debate_id: str, user_id: Optional[str] = None, allow_unscoped: bool = False) -> Optional[DebateRecord]:
        """Finds a debate by ID, optionally restricted to owner user_id. Fail-closed if user_id is None unless allow_unscoped=True."""

    @abstractmethod
    def assign_legacy_debates_to_user(self, user_id: str) -> int:
        """Assigns all pre-auth debates (user_id IS NULL) to a specified user."""

    @abstractmethod
    def delete_by_user_id(self, user_id: str) -> int:
        """Deletes all debates belonging to a specific user."""

    @abstractmethod
    def delete(self, debate_id: str) -> None:
        """Deletes a debate by ID."""
