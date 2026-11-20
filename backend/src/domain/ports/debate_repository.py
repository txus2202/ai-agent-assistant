"""
Domain Port: IDebateRepository
"""
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from src.domain.value_objects.debate_record import DebateRecord, PaginatedDebateSummaries


@runtime_checkable
class IDebateRepository(Protocol):
    """Port for debate record persistence and paginated summary queries."""

    def create(self, debate: DebateRecord) -> None:
        """Saves a new debate record."""
        ...

    def append_event(self, debate_id: str, event_json: str) -> None:
        """Appends a single event to a debate's event log."""
        ...

    def update_status(self, debate_id: str, status: str) -> None:
        """Updates the status of a debate."""
        ...

    def update_session(self, debate_id: str, status: str, target_agent: Optional[str] = None) -> None:
        """Updates status and target agent for an existing continuous debate session."""
        ...

    def find_all(self, user_id: Optional[str] = None, allow_unscoped: bool = False) -> List[DebateRecord]:
        """Returns all debates, optionally filtered by user_id. Fail-closed if user_id is None unless allow_unscoped=True."""
        ...

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
        ...

    def find_by_id(self, debate_id: str, user_id: Optional[str] = None, allow_unscoped: bool = False) -> Optional[DebateRecord]:
        """Finds a debate by ID, optionally restricted to owner user_id. Fail-closed if user_id is None unless allow_unscoped=True."""
        ...

    def assign_legacy_debates_to_user(self, user_id: str) -> int:
        """Assigns all pre-auth debates (user_id IS NULL) to a specified user."""
        ...

    def delete_by_user_id(self, user_id: str) -> int:
        """Deletes all debates belonging to a specific user."""
        ...

    def delete(self, debate_id: str) -> None:
        """Deletes a debate by ID."""
        ...
