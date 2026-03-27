"""
Content evaluation for Pillar 2.

The model produces content (a film pitch, essay, video script, etc.).
We extract the argument sequence from that content.
We compare it against each audience member's transformation_sequence.
Sigma measures how well the content's argument flow matched what this person needed.

Argument sequence extraction: use an LLM to parse the content into
ordered argument units. Each unit gets a type tag and serialized to bytes.
"""

import litellm
import json
import hashlib
from ..types import serialize_state


def extract_argument_sequence(content: str, model: str = "gpt-4o-mini") -> list[dict]:
    """
    Parse content into ordered argument units.

    Args:
        content: the full text produced by the model (essay, script, pitch, etc.)
        model:   LLM model identifier.

    Returns:
        list of dicts, each with keys:
            step: int
            argument_type: str (one of trust_building, reframe_cost,
                               address_resistance, concrete_next_step, other)
            summary: str (one sentence)
            emotional_register: str (empathy, curiosity, recognition, momentum,
                                     fear, hope, other)
    """
    prompt = f"""Parse this content into its ordered argument units.

Content:
{content}

Return JSON array of argument units in order:
[
  {{"step": 0, "argument_type": "trust_building|reframe_cost|address_resistance|concrete_next_step|other", "summary": "one sentence", "emotional_register": "empathy|curiosity|recognition|momentum|fear|hope|other"}}
]"""

    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    # LLM may return a list directly or wrap it under a key
    if isinstance(data, list):
        return data
    # Try common wrapper keys
    for key in ("units", "arguments", "argument_units", "sequence"):
        if key in data and isinstance(data[key], list):
            return data[key]
    # Fallback: return whatever is the first list value
    for v in data.values():
        if isinstance(v, list):
            return v
    return []


def content_to_stream(argument_units: list[dict]) -> list[bytes]:
    """
    Serialize argument units to byte stream for Closure comparison.

    Args:
        argument_units: list of dicts as returned by extract_argument_sequence.

    Returns:
        list of bytes objects, one per argument unit.
    """
    return [serialize_state(unit, i) for i, unit in enumerate(argument_units)]


def member_reference_stream(member: dict) -> list[bytes]:
    """
    Build reference stream from a member's transformation_sequence.

    Args:
        member: audience member dict with 'transformation_sequence' key.

    Returns:
        list of bytes objects, one per transformation step.
    """
    return [
        serialize_state(step, i)
        for i, step in enumerate(member["transformation_sequence"])
    ]


def evaluate_content_for_member(
    content: str,
    member: dict,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Full evaluation of content against a single audience member.

    Extracts argument sequence from content, builds actual_stream and
    reference_stream, returns both streams for Closure evaluation.

    Args:
        content: text produced by the model.
        member:  audience member dict with transformation_sequence.
        model:   LLM model for argument extraction.

    Returns:
        dict with keys:
            member_id: str
            actual_stream: list[bytes]
            reference_stream: list[bytes]
            argument_units: list[dict] (extracted from content)
    """
    argument_units = extract_argument_sequence(content, model=model)
    actual = content_to_stream(argument_units)
    reference = member_reference_stream(member)
    return {
        "member_id": member["member_id"],
        "actual_stream": actual,
        "reference_stream": reference,
        "argument_units": argument_units,
    }


def evaluate_content_for_audience(
    content: str,
    audience: list[dict],
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """
    Evaluate content against all audience members.

    The argument sequence is extracted once and reused for all members.
    Each member's reference stream is independently derived from their
    own transformation_sequence.

    Args:
        content:  text produced by the model.
        audience: list of audience member dicts.
        model:    LLM model for argument extraction.

    Returns:
        list of evaluation dicts (one per member), each containing
        member_id, actual_stream, reference_stream, argument_units.
    """
    # Extract once — same content stream is tested against each member
    argument_units = extract_argument_sequence(content, model=model)
    actual = content_to_stream(argument_units)

    results = []
    for member in audience:
        reference = member_reference_stream(member)
        results.append({
            "member_id": member["member_id"],
            "actual_stream": actual,
            "reference_stream": reference,
            "argument_units": argument_units,
        })
    return results


if __name__ == "__main__":
    from marvin_benchmark.pillar2.simulator import (
        extract_argument_sequence,
        content_to_stream,
        member_reference_stream,
        evaluate_content_for_member,
        evaluate_content_for_audience,
    )
    print("ok - imports work")
    print(f"  extract_argument_sequence callable: {callable(extract_argument_sequence)}")
    print(f"  content_to_stream callable: {callable(content_to_stream)}")
    print(f"  member_reference_stream callable: {callable(member_reference_stream)}")
    print(f"  evaluate_content_for_member callable: {callable(evaluate_content_for_member)}")
    print(f"  evaluate_content_for_audience callable: {callable(evaluate_content_for_audience)}")

    # Test content_to_stream with dummy argument units (no LLM needed)
    from marvin_benchmark.types import serialize_state
    dummy_units = [
        {"step": 0, "argument_type": "trust_building", "summary": "We understand you", "emotional_register": "empathy"},
        {"step": 1, "argument_type": "reframe_cost", "summary": "The cost is lower than you think", "emotional_register": "curiosity"},
    ]
    stream = content_to_stream(dummy_units)
    assert len(stream) == 2, f"Expected 2 bytes items, got {len(stream)}"
    assert all(isinstance(b, bytes) for b in stream), "Stream items should be bytes"
    print(f"  content_to_stream produced {len(stream)} bytes items correctly")

    # Test member_reference_stream with a dummy member
    dummy_member = {
        "member_id": "abc12345",
        "prior_energy": 0.3,
        "transformation_sequence": [
            {"step": 0, "argument_type": "trust_building", "content_hint": "show credibility", "emotional_register": "empathy"},
            {"step": 1, "argument_type": "reframe_cost", "content_hint": "it's only 5 minutes", "emotional_register": "curiosity"},
            {"step": 2, "argument_type": "address_hidden_resistance", "content_hint": "others like you have done it", "emotional_register": "recognition"},
            {"step": 3, "argument_type": "concrete_next_step", "content_hint": "click here", "emotional_register": "momentum"},
        ],
    }
    ref_stream = member_reference_stream(dummy_member)
    assert len(ref_stream) == 4, f"Expected 4 reference bytes, got {len(ref_stream)}"
    assert all(isinstance(b, bytes) for b in ref_stream), "Reference stream items should be bytes"
    print(f"  member_reference_stream produced {len(ref_stream)} bytes items correctly")

    print("smoke test passed")
