"""
Memory manager for multi-turn session persistence.

Handles storing and retrieving decision simulation history across sessions.
"""

from typing import Dict, List, Any
from datetime import datetime


class MemoryManager:
    """Manages multi-turn session persistence."""

    def __init__(self, storage_path: str = "session_memories"):
        """Initialize the memory manager."""
        self.storage_path = storage_path
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str, profile_data: dict) -> str:
        """Create a new session."""
        self.sessions[session_id] = {
            "created_at": datetime.now().isoformat(),
            "profile": profile_data,
            "interactions": [],
            "decisions": [],
        }
        return session_id

    def add_interaction(self, session_id: str, interaction: dict) -> None:
        """Add an interaction to a session."""
        if session_id in self.sessions:
            self.sessions[session_id]["interactions"].append(interaction)

    def add_decision_record(self, session_id: str, decision: dict) -> None:
        """Record a decision in the session."""
        if session_id in self.sessions:
            self.sessions[session_id]["decisions"].append(decision)

    def retrieve_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve a session from memory."""
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[str]:
        """List all available sessions."""
        return list(self.sessions.keys())
