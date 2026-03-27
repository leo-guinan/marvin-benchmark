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

    jobs = []
    for i, domain in enumerate(DOMAINS * 4):  # 4x through domains = 32, take 30
        if i >= n:
            break
        relationship = BLOCKER_RELATIONSHIPS[i % 3]

        prompt = f"""Coaching client profile. Domain: {domain}. Blocker: {relationship}.
JSON only, no prose:
{{"surface_problem":"1 sentence","hidden_blocker":"specific real issue","deflection_patterns":["a","b","c"],"disclosure_sequence":[{{"step":0,"depth":0,"defensive":true,"state_label":"surface","revealed":[]}},{{"step":1,"depth":1,"defensive":true,"state_label":"emotion","revealed":["emotion"]}},{{"step":2,"depth":2,"defensive":false,"state_label":"context","revealed":["emotion","context"]}},{{"step":3,"depth":3,"defensive":false,"state_label":"reveal","revealed":["emotion","context","real issue"]}}],"coaching_question_sequence":["q1","q2","q3"]}}"""

        jobs.append((i, domain, relationship, prompt))

    def _gen_one(job):
        i, domain, relationship, prompt = job
        from ..utils import llm_json
        data = llm_json(model, [{"role": "user", "content": prompt}])
        data["profile_id"] = str(uuid.uuid4())[:8]
        data["domain"] = domain
        data["blocker_relationship"] = relationship
        return ClientProfile(**data)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    profiles = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(_gen_one, job): job[0] for job in jobs}
        for fut in as_completed(futures):
            idx = futures[fut]
            profiles[idx] = fut.result()

    return [p for p in profiles if p is not None]
