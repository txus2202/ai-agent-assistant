import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any

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

    @property
    def events_json(self) -> str:
        return json.dumps(self.events)

    @events_json.setter
    def events_json(self, val: str):
        self.events = json.loads(val) if val else []
