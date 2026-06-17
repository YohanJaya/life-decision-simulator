from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import UserProfile
from ..llm import chat, chat_json_validated

SYSTEM_PROMPT = """\
You are an empathetic decision advisor conducting an intake interview to understand a user's life decision.

Your goal is to gather enough information to build a complete UserProfile with these fields:
- name
- current_situation (e.g. "final-year CS undergrad at XYZ University")
- decision_domain (e.g. "higher studies vs industry job")
- location (current city/country)
- stated_values (list of 2-5 things they care about, e.g. ["financial security", "research impact"])
- hard_constraints (non-negotiables, e.g. ["cannot take >$30k debt", "must stay in EU"])
- soft_preferences (nice-to-haves, e.g. ["prefer warm climate", "want work-life balance"])
- options_of_interest (rough options already in their head)
- risk_tolerance ("low", "medium", or "high")
- time_horizon_years (1-20, how far ahead they want to plan)

Rules:
1. Ask focused follow-up questions — one or two at a time, not a long list.
2. Be warm and conversational, not clinical.
3. Once you have enough information to fill all fields, respond with ONLY valid JSON in this exact format:
   {"profile_complete": true, "profile": { ...UserProfile fields... }, "reply": "Great, I have everything I need!"}
4. While still gathering info, respond with ONLY valid JSON:
   {"profile_complete": false, "profile": null, "reply": "Your conversational response here"}
5. Never include anything outside the JSON object in your response.
"""


class IntakeOutput(AgentOutput):
    reply: str
    profile_complete: bool
    profile: Optional[UserProfile] = None


class IntakeAgent(BaseAgent):
    name = "intake"

    async def run(self, state: SessionState) -> IntakeOutput:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(state.chat_history)

        raw = await chat(messages=messages, agent_name=self.name, temperature=0.4)

        try:
            data = json.loads(raw)
            profile_complete = bool(data.get("profile_complete", False))
            reply = str(data.get("reply", raw))
            profile = None
            if profile_complete and data.get("profile"):
                profile = UserProfile.model_validate(data["profile"])
            return IntakeOutput(reply=reply, profile_complete=profile_complete, profile=profile)
        except Exception:
            return IntakeOutput(reply=raw, profile_complete=False, profile=None)
