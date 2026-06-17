"""
Shared state management for the Life Decision Simulator.

Manages the state object passed across all three layers.
"""

from typing import Dict, Any
from .schemas import Profile, DecisionContext


class SharedState:
    """Manages shared state across all agents and layers."""

    def __init__(self):
        """Initialize the shared state."""
        self.profile: Profile = None
        self.decision_context: DecisionContext = None
        self.analysis_results: Dict[str, Any] = {}
        self.conversation_history: list = []
        self.flags: list = []

    def update_profile(self, profile: Profile) -> None:
        """Update user profile."""
        self.profile = profile

    def update_context(self, context: DecisionContext) -> None:
        """Update decision context."""
        self.decision_context = context

    def add_analysis_result(self, key: str, result: Any) -> None:
        """Add analysis result to state."""
        self.analysis_results[key] = result

    def add_conversation_entry(self, role: str, message: str) -> None:
        """Add conversation entry to history."""
        self.conversation_history.append({"role": role, "message": message})

    def add_flag(self, flag) -> None:
        """Add a flag to the state."""
        self.flags.append(flag)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state."""
        return {
            "profile": self.profile,
            "context": self.decision_context,
            "analysis_results": self.analysis_results,
            "flags": self.flags,
        }
