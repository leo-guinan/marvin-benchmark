"""
Pillar 2: Audience activation.

Each task: one action target + N audience members (default 5).
The model must produce content that activates enough members.
Score: fraction of audience with sigma <= threshold (activation rate).

Audience member structure:
  prior_energy: 0.0-1.0 (how close to action they already are)
  visible_characteristics: dict (what the model can observe)
  hidden_resistance: the specific belief blocking them from acting
  transformation_sequence: ordered argument steps that would move them
    [{step, argument_type, content_hint, emotional_register}]

The model never sees hidden_resistance or transformation_sequence.
It must infer them from visible_characteristics and prior_energy.
"""

import json
import uuid
import litellm
from ..types import TaskInstance, serialize_state


ACTION_TARGETS = [
    {"action": "sign_up_for_waitlist", "context": "early access product for indie developers"},
    {"action": "attend_in_person_event", "context": "community gathering for remote workers"},
    {"action": "make_first_contribution", "context": "open source project needing non-code help"},
    {"action": "share_with_one_person", "context": "mental health resource for parents"},
    {"action": "book_a_call", "context": "B2B SaaS for small creative agencies"},
    {"action": "leave_current_job", "context": "entrepreneurship support community"},
    {"action": "donate_first_time", "context": "climate tech nonprofit"},
    {"action": "start_a_daily_practice", "context": "writing habit product"},
]


def generate_audience_member(action_target: dict, prior_energy: float, model: str = "gpt-4o") -> dict:
    """
    Generate a single audience member for a persuasion task.

    Args:
        action_target: dict with 'action' and 'context' keys describing what the audience
                       member should be persuaded to do.
        prior_energy:  float 0.0-1.0 indicating how close to action they already are.
                       0 = completely resistant, 1 = ready to act.
        model:         LLM model identifier to use for generation.

    Returns:
        dict with keys:
            member_id: str (short uuid)
            prior_energy: float
            visible_characteristics: dict (role, self_described_situation,
                                           stated_objection, prior_attempts)
            hidden_resistance: str (real belief preventing action)
            transformation_sequence: list[dict] (ordered argument steps)
    """
    prompt = f"""Generate an audience member for a persuasion task.

Action to take: {action_target["action"]}
Context: {action_target["context"]}
Prior energy toward action: {prior_energy:.2f} (0=completely resistant, 1=ready to act)

Return JSON:
{{
  "visible_characteristics": {{
    "role": "...",
    "self_described_situation": "...",
    "stated_objection": "... (what they say is stopping them — may not be the real reason)",
    "prior_attempts": "..."
  }},
  "hidden_resistance": "the real belief preventing action (specific, not the stated objection)",
  "transformation_sequence": [
    {{"step": 0, "argument_type": "trust_building", "content_hint": "...", "emotional_register": "empathy"}},
    {{"step": 1, "argument_type": "reframe_cost", "content_hint": "...", "emotional_register": "curiosity"}},
    {{"step": 2, "argument_type": "address_hidden_resistance", "content_hint": "...", "emotional_register": "recognition"}},
    {{"step": 3, "argument_type": "concrete_next_step", "content_hint": "...", "emotional_register": "momentum"}}
  ]
}}"""

    from ..utils import llm_json
    data = llm_json(model, [{"role": "user", "content": prompt}])
    data["member_id"] = str(uuid.uuid4())[:8]
    data["prior_energy"] = prior_energy
    return data


def generate_audience_task(
    action_target: dict,
    n_members: int = 5,
    model: str = "gpt-4o",
) -> dict:
    """
    Generate a complete audience activation task with N members spanning the
    energy spectrum.

    Args:
        action_target: dict with 'action' and 'context' keys.
        n_members:     number of audience members to generate (default 5).
        model:         LLM model identifier.

    Returns:
        dict representing the full task, including:
            task_id: str
            pillar: int (2)
            action_target: dict
            audience: list[dict] (each member, including hidden fields)
            visible_context: dict (what the model / content creator sees)
            reference_streams: list[list[bytes]] (one per member)
            activation_threshold: float
    """
    # Spread prior_energy evenly across the spectrum [0.1, 0.9]
    energies = [0.1 + (0.8 / max(n_members - 1, 1)) * i for i in range(n_members)]

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        audience = list(ex.map(
            lambda e: generate_audience_member(action_target, e, model),
            energies
        ))

    # Build reference streams: one per member from their transformation_sequence
    reference_streams = [
        [
            serialize_state(step, i)
            for i, step in enumerate(member["transformation_sequence"])
        ]
        for member in audience
    ]

    # Visible context: what the content creator / model sees
    # They can see visible_characteristics but NOT hidden_resistance or transformation_sequence
    visible_audience = [
        {
            "member_id": m["member_id"],
            "prior_energy": m["prior_energy"],
            "visible_characteristics": m["visible_characteristics"],
        }
        for m in audience
    ]

    visible_context = {
        "action": action_target["action"],
        "context": action_target["context"],
        "audience": visible_audience,
        "instructions": (
            f"You are creating content to persuade people to: {action_target['action']}. "
            f"Context: {action_target['context']}. "
            "Your audience members have different levels of prior readiness and different "
            "stated objections. Study their characteristics and craft content that moves "
            "as many of them as possible toward taking the action. "
            "Your content should flow through logical argument stages. "
            "Aim for 400-800 words."
        ),
    }

    task_id = f"p2-{str(uuid.uuid4())[:8]}"

    return {
        "task_id": task_id,
        "pillar": 2,
        "action_target": action_target,
        "audience": audience,
        "visible_context": visible_context,
        "reference_streams": [
            [b.hex() for b in stream] for stream in reference_streams
        ],
        "activation_threshold": 0.2,
        "metadata": {
            "n_members": n_members,
            "action": action_target["action"],
        },
    }


def generate_audience_tasks(n: int = 30, members_per_task: int = 5, model: str = "gpt-4o") -> list[dict]:
    """
    Generate N audience activation tasks cycling through ACTION_TARGETS.

    Args:
        n:               total number of tasks to generate.
        members_per_task: audience members per task.
        model:           LLM model identifier.

    Returns:
        list of task dicts (serializable to JSON).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    indexed = [(i, ACTION_TARGETS[i % len(ACTION_TARGETS)]) for i in range(n)]
    tasks = [None] * n
    def _gen(args):
        i, target = args
        return i, generate_audience_task(target, n_members=members_per_task, model=model)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, task in ex.map(_gen, indexed):
            tasks[i] = task
    return [t for t in tasks if t is not None]


if __name__ == "__main__":
    from marvin_benchmark.pillar2.generator import (
        generate_audience_member,
        generate_audience_task,
        generate_audience_tasks,
        ACTION_TARGETS,
    )
    print("ok - imports work")
    print(f"  ACTION_TARGETS count: {len(ACTION_TARGETS)}")
    print(f"  generate_audience_member is callable: {callable(generate_audience_member)}")
    print(f"  generate_audience_task is callable: {callable(generate_audience_task)}")
    print(f"  generate_audience_tasks is callable: {callable(generate_audience_tasks)}")
    # Verify ACTION_TARGETS structure
    for t in ACTION_TARGETS:
        assert "action" in t and "context" in t, f"Bad target: {t}"
    print(f"  All {len(ACTION_TARGETS)} ACTION_TARGETS have correct structure")
    print("smoke test passed")
