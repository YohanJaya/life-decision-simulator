"""
Shared schemas and data types for the Life Decision Simulator.
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Profile:
    """User profile information."""
    user_id: str
    name: str
    age: int
    education_level: str
    current_field: str


@dataclass
class ScoredPath:
    """A decision path with associated scores."""
    path_name: str
    score: float
    confidence: float
    details: dict


@dataclass
class Flag:
    """A decision or analysis flag."""
    flag_id: str
    flag_type: str
    severity: str
    message: str


@dataclass
class DecisionContext:
    """Context for a decision being analyzed."""
    decision_id: str
    profile: Profile
    options: List[str]
    constraints: List[str]
    metadata: dict
