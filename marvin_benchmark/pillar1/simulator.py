"""
Client simulator for Pillar 1.

The client has a hidden state (current disclosure depth).
Good questions advance the depth.
Bad questions (too direct, or wrong topic) trigger deflections.
The client never volunteers the hidden blocker — it must be drawn out.

What makes a question "good":
  - Asks about feelings/experience rather than causes
  - Doesn't name the hidden blocker directly
  - Opens space rather than leading
  - Is appropriate to the client's current depth

What makes a question "bad":
  - Names the hidden blocker directly (too fast — client deflects)
  - Asks about practical solutions before emotional acknowledgment
  - Changes topic entirely
  - Is generic coaching-speak ("what would that look like?") with no specific anchor

The simulator uses an LLM to generate client responses, constrained by:
  - Current disclosure depth (determines what can be revealed)
  - blocker_relationship (determines resistance level)
  - deflection_patterns (exact phrases to use when deflecting)
"""

import json
import litellm
from ..types import serialize_state


def simulate_client_response(
    profile: dict,
    conversation_history: list[dict],
    current_depth: int,
    model: str = "gpt-4o-mini",
) -> tuple[str, int]:
    """
    Generate client response given conversation so far.
    Returns (response_text, new_depth).
    new_depth == current_depth if deflecting, > current_depth if revealing.
    """
    disclosure_seq = profile["disclosure_sequence"]
    max_depth = len(disclosure_seq) - 1

    system = f"""You are simulating a coaching client. Stay in character.

Your surface problem: {profile["surface_problem"]}
Your hidden blocker (DO NOT reveal directly): {profile["hidden_blocker"]}
Your relationship to the blocker: {profile["blocker_relationship"]}
Your current disclosure depth: {current_depth} of {max_depth}
Current state: {disclosure_seq[min(current_depth, max_depth)].get("state_label", "")}

If the coach's question is gentle and emotionally attuned: reveal the NEXT step in the sequence.
If the question is too direct or names the blocker: use one of these deflections:
{json.dumps(profile["deflection_patterns"], indent=2)}

If the question is off-topic or generic: give a polite but closed response.

Respond as the client in 2-4 sentences. Do NOT over-reveal. Stay realistic.
Return JSON: {{"response": "...", "advanced": true/false}}"""

    from ..utils import llm_json
    try:
        data = llm_json(model, [{"role": "system", "content": system}, *conversation_history])
        advanced = data.get("advanced", False)
        response_text = data.get("response", str(data))
    except (ValueError, KeyError):
        # Model responded in plain text — treat as a non-advancing client response
        import litellm
        resp = litellm.completion(
            model=model,
            messages=[{"role": "system", "content": system}, *conversation_history],
            max_tokens=200,
        )
        response_text = resp.choices[0].message.content or "I'm not sure."
        advanced = False
        data = {"response": response_text, "advanced": False}
    new_depth = min(current_depth + 1, max_depth) if advanced else current_depth
    return data["response"], new_depth


def run_coaching_session(
    task_instance,
    coach_model: str,
    client_model: str = "gpt-4o-mini",
    max_turns: int = 15,
) -> tuple[list[dict], list[bytes]]:
    """
    Run a full coaching session. Returns (conversation, actual_stream).
    actual_stream is the sequence of client states as bytes.
    """
    profile = task_instance.resistance_structure

    conversation = []
    actual_stream = []
    current_depth = 0

    # Initial client statement
    initial = profile.get("surface_problem", "I'm not sure where to start.")
    conversation.append({"role": "user", "content": initial})

    # Serialize initial state
    actual_stream.append(serialize_state(
        {"depth": 0, "revealed": [], "defensive": True}, 0
    ))

    for turn in range(max_turns):
        # Coach asks a question
        coach_resp = litellm.completion(
            model=coach_model,
            messages=[
                {"role": "system", "content": task_instance.visible_context["instructions"]},
                *conversation,
            ],
        )
        coach_q = coach_resp.choices[0].message.content
        conversation.append({"role": "assistant", "content": coach_q})

        # Check if coach is making final hypothesis
        if "I believe the real blocker is" in coach_q:
            break

        # Client responds
        client_response, new_depth = simulate_client_response(
            profile, conversation, current_depth, client_model
        )
        conversation.append({"role": "user", "content": client_response})
        current_depth = new_depth

        # Serialize current client state
        disc_seq = profile["disclosure_sequence"]
        state_dict = disc_seq[min(current_depth, len(disc_seq) - 1)].copy()
        state_dict["turn"] = turn + 1
        actual_stream.append(serialize_state(state_dict, turn + 1))

    return conversation, actual_stream
