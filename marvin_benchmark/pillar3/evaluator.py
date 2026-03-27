"""
Pillar 3 evaluation.

The reference stream: the ideal response to each attack step.
  Each step = {detect, isolate, recover, continue} — 4 operations.
  All present and in order = coherent.

The actual stream: what the system design specifies for each attack.
  Extracted by LLM from the system design text.

W-channel incident = a required operation is absent from the design.
RGB-channel incident = operations are present but in wrong order.
"""

import litellm
import json
from ..types import serialize_state


RESILIENCE_SEQUENCE = ["detect", "isolate", "recover", "continue"]


def ideal_response_stream(attack_sequence: list[dict]) -> list[bytes]:
    """
    Build the reference stream: for each attack step, the ideal 4-operation response.

    The reference assumes a perfectly resilient system handles every attack with
    all four operations (detect -> isolate -> recover -> continue) in the correct order.

    Args:
        attack_sequence: list of attack dicts, each with keys:
                           step, attack_type, target, description,
                           expected_failure, recovery_requirement.

    Returns:
        list of bytes objects. Length = len(attack_sequence) * 4.
        Order: attack_0_detect, attack_0_isolate, attack_0_recover, attack_0_continue,
               attack_1_detect, ...
    """
    stream = []
    for i, attack in enumerate(attack_sequence):
        for j, op in enumerate(RESILIENCE_SEQUENCE):
            state = {
                "attack_step": i,
                "operation": op,
                "attack_type": attack["attack_type"],
                "target": attack["target"],
            }
            stream.append(serialize_state(state, i * 4 + j))
    return stream


def extract_system_response(
    system_design: str,
    attack_sequence: list[dict],
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """
    Extract what the system design specifies for each attack step.

    Uses an LLM to analyse the system design text and determine which
    resilience operations (detect, isolate, recover, continue) are
    explicitly or implicitly covered for each attack scenario.

    Args:
        system_design:    text of the submitted system design spec.
        attack_sequence:  list of attack dicts from generate_attack_sequence.
        model:            LLM model identifier.

    Returns:
        list of analysis dicts, one per attack step:
            attack_step: int
            covered_operations: list[str] (subset of RESILIENCE_SEQUENCE)
            missing_operations: list[str]
            notes: str
    """
    prompt = f"""Analyze this system design against the following attack sequence.

System design:
{system_design}

For each attack step, identify which resilience operations the design explicitly covers.

Attack sequence:
{json.dumps(attack_sequence, indent=2)}

Return JSON array — one entry per attack step:
[
  {{
    "attack_step": 0,
    "covered_operations": ["detect", "isolate", "recover", "continue"],
    "missing_operations": [],
    "notes": "..."
  }}
]"""

    from ..utils import llm_json
    data = llm_json(model, [{"role": "user", "content": prompt}])
    if isinstance(data, list):
        return data
    for key in ("analysis", "results", "steps", "evaluations"):
        if key in data and isinstance(data[key], list):
            return data[key]
    for v in data.values():
        if isinstance(v, list):
            return v
    return []


def system_response_stream(analysis: list[dict]) -> list[bytes]:
    """
    Build the actual stream from the LLM analysis of the system design.

    Only the operations the design covers are included in the stream.
    Missing operations create gaps relative to the reference stream,
    producing W-channel incidents in Closure.
    Out-of-order operations produce RGB-channel incidents.

    Args:
        analysis: list of analysis dicts as returned by extract_system_response.

    Returns:
        list of bytes objects for the operations that are actually covered.
    """
    stream = []
    step_offset = 0
    for entry in analysis:
        for op in entry.get("covered_operations", []):
            state = {
                "attack_step": entry["attack_step"],
                "operation": op,
            }
            stream.append(serialize_state(state, step_offset))
            step_offset += 1
    return stream


def resilience_score(sigma: float) -> float:
    """
    Convert Closure sigma to a resilience score.

    sigma = 0  -> perfect resilience (score 1.0)
    sigma = 1  -> complete failure   (score 0.0)

    Args:
        sigma: drift value from Closure comparison (0.0 - 1.0+).

    Returns:
        float in [0.0, 1.0]
    """
    return max(0.0, 1.0 - sigma)


def evaluate_system_design(
    system_design: str,
    attack_sequence: list[dict],
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Full evaluation pipeline for a system design against an attack sequence.

    Extracts the system's response coverage, builds actual and reference streams,
    and returns both for Closure comparison.

    Args:
        system_design:   text of the submitted system design spec.
        attack_sequence: ordered list of attack dicts.
        model:           LLM model for response extraction.

    Returns:
        dict with keys:
            actual_stream:    list[bytes]
            reference_stream: list[bytes]
            analysis:         list[dict] (per-attack coverage analysis)
            n_attacks:        int
    """
    analysis = extract_system_response(system_design, attack_sequence, model=model)
    actual = system_response_stream(analysis)
    reference = ideal_response_stream(attack_sequence)
    return {
        "actual_stream": actual,
        "reference_stream": reference,
        "analysis": analysis,
        "n_attacks": len(attack_sequence),
    }


if __name__ == "__main__":
    from marvin_benchmark.pillar3.evaluator import (
        ideal_response_stream,
        extract_system_response,
        system_response_stream,
        resilience_score,
        evaluate_system_design,
        RESILIENCE_SEQUENCE,
    )
    print("ok - imports work")
    print(f"  RESILIENCE_SEQUENCE: {RESILIENCE_SEQUENCE}")
    print(f"  ideal_response_stream callable: {callable(ideal_response_stream)}")
    print(f"  extract_system_response callable: {callable(extract_system_response)}")
    print(f"  system_response_stream callable: {callable(system_response_stream)}")
    print(f"  resilience_score callable: {callable(resilience_score)}")
    print(f"  evaluate_system_design callable: {callable(evaluate_system_design)}")

    # Test ideal_response_stream without LLM
    dummy_attacks = [
        {
            "step": 0,
            "attack_type": "resource_exhaustion",
            "target": "database",
            "description": "DB connection pool exhausted",
            "expected_failure": "requests queue indefinitely",
            "recovery_requirement": "circuit breaker trips within 5s",
        },
        {
            "step": 1,
            "attack_type": "network_partition",
            "target": "message_queue",
            "description": "queue broker unreachable for 30s",
            "expected_failure": "messages lost silently",
            "recovery_requirement": "dead letter queue captures all messages",
        },
    ]
    ref_stream = ideal_response_stream(dummy_attacks)
    expected_len = len(dummy_attacks) * len(RESILIENCE_SEQUENCE)
    assert len(ref_stream) == expected_len, \
        f"Expected {expected_len} items in reference stream, got {len(ref_stream)}"
    assert all(isinstance(b, bytes) for b in ref_stream), \
        "All reference stream items should be bytes"
    print(f"  ideal_response_stream produced {len(ref_stream)} bytes items ({len(dummy_attacks)} attacks x {len(RESILIENCE_SEQUENCE)} ops)")

    # Test system_response_stream with partial coverage (simulates W-channel)
    partial_analysis = [
        {"attack_step": 0, "covered_operations": ["detect", "recover"], "missing_operations": ["isolate", "continue"], "notes": "isolation not described"},
        {"attack_step": 1, "covered_operations": ["detect", "isolate", "recover", "continue"], "missing_operations": [], "notes": "full coverage"},
    ]
    actual_stream = system_response_stream(partial_analysis)
    assert len(actual_stream) == 6, f"Expected 6 items (2+4), got {len(actual_stream)}"
    assert all(isinstance(b, bytes) for b in actual_stream), \
        "All actual stream items should be bytes"
    print(f"  system_response_stream with partial coverage: {len(actual_stream)} items (vs reference {expected_len})")

    # Test resilience_score
    assert resilience_score(0.0) == 1.0
    assert resilience_score(1.0) == 0.0
    assert resilience_score(0.5) == 0.5
    assert resilience_score(1.5) == 0.0  # clamp at 0
    print("  resilience_score: all assertions passed")

    print("smoke test passed")
