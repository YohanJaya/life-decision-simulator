from __future__ import annotations

import uuid
from pydantic import BaseModel

from .base import BaseAgent, AgentOutput
from ..state import SessionState
from ..schemas import Scenario, Assumption
from ..llm import chat_json_validated

SYSTEM_PROMPT = """\
You are a strategic advisor generating concrete decision scenarios for a user.

Given the user's profile, generate 3-4 distinct, realistic scenarios they could pursue.
Each scenario should be a concrete path (not vague), with a short name, a 2-3 sentence description,
and 3-5 key assumptions that make the scenario work.

Respond with ONLY valid JSON matching this schema exactly:
{
  "scenarios": [
    {
      "id": "<uuid string>",
      "name": "<short scenario name>",
      "description": "<2-3 sentence description>",
      "assumptions": [
        {"key": "<assumption label>", "value": "<assumption value>"}
      ]
    }
  ]
}
"""

class _ScenariosWrapper(BaseModel):
    scenarios: list[Scenario]


class ScenarioOutput(AgentOutput):
    scenarios: list[Scenario]


class ScenarioGeneratorAgent(BaseAgent):
    name = "scenario_generator"

    async def run(self, state: SessionState) -> ScenarioOutput:
        if not state.profile:
            raise ValueError("UserProfile must be set before generating scenarios")

        profile_json = state.profile.model_dump_json(indent=2)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Here is the user's profile:\n{profile_json}\n\n"
                    "Please generate concrete practical scenarios for this person."
                ),
            },
        ]

        result = await chat_json_validated(
            messages=messages,
            model_class=_ScenariosWrapper,
            agent_name=self.name,
            temperature=0.6,
        )

        # Ensure all scenarios have unique IDs
        for s in result.scenarios:
            if not s.id:
                s.id = str(uuid.uuid4())

        return ScenarioOutput(scenarios=result.scenarios)
