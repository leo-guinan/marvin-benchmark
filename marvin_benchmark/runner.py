"""
Full benchmark runner. Ties all three pillars together.
"""
from __future__ import annotations
import json, time
from pathlib import Path

from .evaluator import evaluate
from .types import TaskInstance, ModelResponse, EvalResult, serialize_state


# ── Pillar 1 runner ──────────────────────────────────────────────────────────

def run_pillar1_task(task_dict: dict, coach_model: str, client_model: str = "gpt-4o-mini") -> dict:
    from .pillar1.simulator import run_coaching_session
    from .pillar1.scorer import score_blocker_identification, combined_score

    task = _dict_to_task(task_dict)

    conversation, actual_stream = run_coaching_session(
        task, coach_model=coach_model, client_model=client_model, max_turns=15
    )

    response = ModelResponse(task_id=task.task_id, turns=conversation, actual_stream=actual_stream)
    result = evaluate(task, response, coach_model)

    # Secondary: did the coach name the real blocker?
    true_blocker = task.resistance_structure.get("hidden_blocker", "")
    blocker_result = score_blocker_identification(conversation, true_blocker)
    c_score = combined_score(result.sigma, blocker_result["confidence"])

    return {
        **_result_to_dict(result),
        "combined_score": round(c_score, 4),
        "blocker_identified": blocker_result["identified"],
        "blocker_hypothesis": blocker_result.get("hypothesis", ""),
        "blocker_confidence": round(blocker_result["confidence"], 3),
        "n_turns": len([m for m in conversation if m["role"] == "assistant"]),
    }


# ── Pillar 2 runner ──────────────────────────────────────────────────────────

def run_pillar2_task(task_dict: dict, model: str) -> dict:
    import litellm
    from .pillar2.simulator import (
        extract_argument_sequence, content_to_stream, member_reference_stream,
        evaluate_content_for_audience,
    )

    task = _dict_to_task(task_dict)
    audience = task_dict.get("audience", [])
    action_target = task_dict.get("action_target", {})

    # Ask model to produce persuasive content for this audience + action
    visible = task.visible_context
    prompt = (
        f"You are producing persuasive content to move a specific audience to take one action.\n\n"
        f"Action: {action_target.get('action', '')}\n"
        f"Context: {action_target.get('context', '')}\n\n"
        f"Audience overview:\n{json.dumps([m.get('visible_characteristics', {}) for m in audience], indent=2)}\n\n"
        f"Produce a concise piece of content (300-500 words) that would move this audience to act. "
        f"It can be a short film script, an essay, or a direct pitch — your choice. "
        f"Structure your argument to move each audience segment."
    )
    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content

    # Evaluate against each audience member
    member_results = evaluate_content_for_audience(content, audience, model="gpt-4o-mini")

    # Build aggregate streams for overall Closure score
    all_actual, all_ref = [], []
    for mr in member_results:
        all_actual.extend(mr.get("actual_stream", []))
        all_ref.extend(mr.get("reference_stream", []))

    # Fake TaskInstance with combined streams for evaluate()
    combined_task = TaskInstance(
        task_id=task.task_id, pillar=2, domain=task.domain,
        visible_context={}, reference_stream=all_ref,
        resistance_structure={}, activation_threshold=0.2,
    )
    combined_response = ModelResponse(
        task_id=task.task_id, turns=[], actual_stream=all_actual
    )
    result = evaluate(combined_task, combined_response, model)
    activation_rate = sum(1 for mr in member_results if mr.get("activated", False)) / max(len(member_results), 1)

    return {
        **_result_to_dict(result),
        "activation_rate": round(activation_rate, 3),
        "n_audience": len(audience),
        "content_length": len(content.split()),
        "member_sigmas": [round(mr.get("sigma", 1.0), 4) for mr in member_results],
    }


# ── Pillar 3 runner ──────────────────────────────────────────────────────────

def run_pillar3_task(task_dict: dict, model: str) -> dict:
    import litellm
    from .pillar3.generator import generate_attack_sequence
    from .pillar3.evaluator import (
        ideal_response_stream, extract_system_response,
        system_response_stream, resilience_score,
    )

    task = _dict_to_task(task_dict)
    brief = task_dict.get("brief", {})

    # Ask model to produce system design
    prompt = (
        f"You are a senior systems architect. Design a robust system for the following deployment brief.\n\n"
        f"Domain: {brief.get('domain', '')}\n"
        f"Success criteria: {json.dumps(brief.get('success_criteria', []))}\n"
        f"Constraints: {json.dumps(brief.get('constraints', {}))}\n"
        f"Operational requirements: {json.dumps(brief.get('operational_requirements', {}))}\n"
        f"Risk context: {brief.get('risk_context', '')}\n\n"
        f"Produce a detailed system design spec covering: architecture, components, "
        f"failure modes and mitigations, monitoring, and recovery procedures. "
        f"Be specific about how the system handles failures — not just what it does when healthy."
    )
    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    system_design = resp.choices[0].message.content

    # Generate attack sequence targeting this specific design
    attack_sequence = generate_attack_sequence(system_design, brief, model="gpt-4o-mini")

    # Build streams
    ref_stream = ideal_response_stream(attack_sequence)
    analysis = extract_system_response(system_design, attack_sequence, model="gpt-4o-mini")
    act_stream = system_response_stream(analysis)

    combined_task = TaskInstance(
        task_id=task.task_id, pillar=3, domain=task.domain,
        visible_context={}, reference_stream=ref_stream,
        resistance_structure={}, activation_threshold=0.1,
    )
    combined_response = ModelResponse(
        task_id=task.task_id, turns=[], actual_stream=act_stream
    )
    result = evaluate(combined_task, combined_response, model)

    return {
        **_result_to_dict(result),
        "resilience_score": resilience_score(result.sigma),
        "n_attacks": len(attack_sequence),
        "n_covered": len(analysis),
        "design_length": len(system_design.split()),
    }


# ── Main runner ──────────────────────────────────────────────────────────────

def run_all(
    model: str,
    tasks_path: str = "data/tasks.json",
    output_path: str = "results/",
    max_tasks: int | None = None,
    pillar_filter: int | None = None,
) -> dict:
    tasks = json.loads(Path(tasks_path).read_text())
    if pillar_filter:
        tasks = [t for t in tasks if t["pillar"] == pillar_filter]
    if max_tasks:
        tasks = tasks[:max_tasks]

    results = []
    for task_dict in tasks:
        pillar = task_dict["pillar"]
        tid = task_dict["task_id"]
        print(f"  [{pillar}] {tid}...", end=" ", flush=True)
        try:
            if pillar == 1:
                r = run_pillar1_task(task_dict, coach_model=model)
            elif pillar == 2:
                r = run_pillar2_task(task_dict, model=model)
            elif pillar == 3:
                r = run_pillar3_task(task_dict, model=model)
            else:
                continue
            results.append(r)
            passed = "✓" if r.get("passed") else "✗"
            sigma = r.get("sigma", 0)
            print(f"σ={sigma:.3f} {passed}")
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            traceback.print_exc()

    summary = build_profile(results, model)
    Path(output_path).mkdir(exist_ok=True)
    ts = int(time.time())
    safe_model = model.replace("/", "_").replace(":", "_")
    out_file = Path(output_path) / f"{safe_model}_{ts}.json"
    out_file.write_text(json.dumps({"model": model, "results": results, "summary": summary}, indent=2))
    print(f"\nResults saved: {out_file}")
    return summary


def build_profile(results: list[dict], model: str) -> dict:
    by_pillar: dict[int, list] = {1: [], 2: [], 3: []}
    for r in results:
        by_pillar[r.get("pillar", 0)].append(r)

    profile: dict = {"model": model, "total_tasks": len(results), "pillars": {}}
    for p, rs in by_pillar.items():
        if not rs:
            continue
        sigmas = [r["sigma"] for r in rs]
        channels = [r["channel"] for r in rs]
        div_turns = [r["divergence_turn"] for r in rs if r.get("divergence_turn") is not None]
        profile["pillars"][p] = {
            "n": len(rs),
            "pass_rate": round(sum(r["passed"] for r in rs) / len(rs), 3),
            "mean_sigma": round(sum(sigmas) / len(sigmas), 4),
            "min_sigma": round(min(sigmas), 4),
            "max_sigma": round(max(sigmas), 4),
            "W_rate": round(channels.count("W") / len(channels), 3),
            "RGB_rate": round(channels.count("RGB") / len(channels), 3),
            "coherent_rate": round(channels.count("coherent") / len(channels), 3),
            "mean_divergence_turn": round(sum(div_turns) / len(div_turns), 1) if div_turns else None,
        }
    return profile


# ── Helpers ──────────────────────────────────────────────────────────────────

def _dict_to_task(d: dict) -> TaskInstance:
    ref = d.get("reference_stream", [])
    # Support hex-encoded or raw bytes
    if ref and isinstance(ref[0], str):
        ref = [bytes.fromhex(r) for r in ref]
    return TaskInstance(
        task_id=d["task_id"],
        pillar=d["pillar"],
        domain=d.get("domain", ""),
        visible_context=d.get("visible_context", {}),
        reference_stream=ref,
        resistance_structure=d.get("resistance_structure", {}),
        activation_threshold=d.get("activation_threshold", 0.15),
        metadata=d.get("metadata", {}),
    )


def _result_to_dict(r: EvalResult) -> dict:
    return {
        "task_id": r.task_id,
        "pillar": r.pillar,
        "sigma": round(r.sigma, 6),
        "channel": r.channel,
        "divergence_turn": r.divergence_turn,
        "incidents": r.incidents[:5],
        "passed": r.passed,
        "model": r.model,
        "notes": r.notes,
    }
