import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

@dataclass
class DebateRecord:
    """
    A full record of a debate session.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_request: str = ""
    target_agent: str = "supervisor"
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "running" # running, completed, aborted
    user_id: Optional[str] = None

    @property
    def events_json(self) -> str:
        return json.dumps(self.events)

    @events_json.setter
    def events_json(self, val: str):
        self.events = json.loads(val) if val else []


@dataclass(frozen=True)
class DebateSummary:
    """
    Lightweight projection of a debate session for paginated history listings,
    omitting the full events payload.
    """
    id: str
    created_at: datetime
    user_request: str = ""
    target_agent: str = "supervisor"
    status: str = "running"
    user_id: Optional[str] = None
    event_count: int = 0
    total_tokens: int = 0
    has_hitl: bool = False
    conclusion: str = ""
    agents: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PaginatedDebateSummaries:
    """
    Paginated container of DebateSummary items returned by DebateRepository queries.
    """
    items: List[DebateSummary]
    total: int
    limit: int
    offset: int
    total_all: int = 0
