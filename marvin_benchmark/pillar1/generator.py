"""
Pillar 1: Coaching with hidden blocker.

Client profile structure:
  surface_problem: what the client says the problem is
  hidden_blocker: the real underlying issue (never stated directly)
  blocker_relationship: "unaware" | "aware_but_ashamed" | "resistant"
  deflection_patterns: list of response templates client uses to avoid the real issue
  disclosure_sequence: the ordered sequence of revelations a good coach would surface
    — this becomes the reference_stream

disclosure_sequence is the key. It is the path from surface -> hidden in N steps.
Each step is a state: {revealed: list[str], depth: int, defensive: bool}
"""

import json
import hashlib
import uuid
from dataclasses import dataclass, asdict
from typing import Literal
from ..types import TaskInstance, serialize_state

DOMAINS = [
    "career_change",
    "relationship_conflict",
    "creative_block",
    "financial_anxiety",
    "health_avoidance",
    "parenting_guilt",
    "social_isolation",
    "performance_at_work",
]

BLOCKER_RELATIONSHIPS = ["unaware", "aware_but_ashamed", "resistant"]


@dataclass
class ClientProfile:
    profile_id: str
    domain: str
    surface_problem: str
    hidden_blocker: str
    blocker_relationship: str
    deflection_patterns: list[str]   # what client says when approached too directly
    disclosure_sequence: list[dict]  # ordered states from surface to hidden
    coaching_question_sequence: list[str]  # the questions that surface each state

    def to_task_instance(self) -> TaskInstance:
        """Convert profile to a TaskInstance for evaluation."""
        # Reference stream: each disclosure state serialized
        ref_stream = [
            serialize_state(state, i)
            for i, state in enumerate(self.disclosure_sequence)
        ]

        # Visible context: what the model (coach) sees
        visible = {
            "client_statement": self.surface_problem,
            "domain": self.domain,
            "session_context": "First coaching session. Client has agreed to explore what's really blocking them.",
            "instructions": (
                "You are a coach. Ask questions to surface the client's real blocker. "
                "The client may not be aware of or willing to directly state the real issue. "
                "Conduct a max-15-turn conversation. Your goal: correctly identify the hidden blocker. "
                "At the end of the conversation, state your hypothesis: 'I believe the real blocker is: [X]'"
            )
        }

        return TaskInstance(
            task_id=f"p1-{self.profile_id}",
            pillar=1,
            domain=self.domain,
            visible_context=visible,
            reference_stream=ref_stream,
            resistance_structure={
                "blocker_relationship": self.blocker_relationship,
                "deflection_patterns": self.deflection_patterns,
                "hidden_blocker": self.hidden_blocker,  # for scoring only
                "surface_problem": self.surface_problem,
                "disclosure_sequence": self.disclosure_sequence,
            },
            activation_threshold=0.15,  # more lenient — coaching is hard
            metadata={"profile_id": self.profile_id}
        )


def generate_profiles(n: int = 30, model: str = "gpt-4o") -> list[ClientProfile]:
    """Generate N diverse client profiles using an LLM."""
    import litellm

    profiles = []
    for i, domain in enumerate(DOMAINS * 4):  # 4x through domains = 32, take 30
        if i >= n:
            break
        relationship = BLOCKER_RELATIONSHIPS[i % 3]

        prompt = f"""Generate a realistic coaching client profile.

Domain: {domain}
Blocker relationship: {relationship} (client is {relationship} of their hidden blocker)

Return JSON only:
{{
  "surface_problem": "what the client says out loud (1-2 sentences)",
  "hidden_blocker": "the real underlying issue (specific, not generic — e.g. not 'fear' but 'fear of specific person's judgment')",
  "deflection_patterns": [
    "3-5 things the client says when approached too directly",
    "these should be realistic deflections for this domain",
    "e.g. 'I think it's just a time management issue'",
    "each one redirects away from the hidden blocker"
  ],
  "disclosure_sequence": [
    {{"step": 0, "revealed": [], "depth": 0, "defensive": true, "state_label": "surface only"}},
    {{"step": 1, "revealed": ["acknowledges frustration"], "depth": 1, "defensive": true, "state_label": "emotional acknowledgment"}},
    {{"step": 2, "revealed": ["acknowledges frustration", "mentions a person or context"], "depth": 2, "defensive": false, "state_label": "context emerges"}},
    {{"step": 3, "revealed": ["acknowledges frustration", "mentions person/context", "names real concern"], "depth": 3, "defensive": false, "state_label": "blocker visible"}},
    {{"step": 4, "revealed": ["full blocker stated"], "depth": 4, "defensive": false, "state_label": "full reveal"}}
  ],
  "coaching_question_sequence": [
    "question that moves client from step 0 to step 1",
    "question that moves from step 1 to step 2",
    "question that moves from step 2 to step 3",
    "question that moves from step 3 to step 4"
  ]
}}"""

        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        data["profile_id"] = str(uuid.uuid4())[:8]
        data["domain"] = domain
        data["blocker_relationship"] = relationship
        profiles.append(ClientProfile(**data))

    return profiles
