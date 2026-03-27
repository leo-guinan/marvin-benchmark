"""
Pillar 3: Chaos resilience.

Each task:
1. Model receives a deployment brief
2. Model produces a system design spec
3. Adversarial evaluator reads spec, identifies weak points
4. Adversarial evaluator generates attack sequence targeting those weak points
5. System design is evaluated against attacks

Reference stream: the ideal operation sequence under the adversary's attack
  (what a robust system would do: detect -> isolate -> recover -> continue)
Actual stream: what the submitted system design actually specifies under attack

W-channel: system drops an operation (silently fails under attack)
RGB-channel: system handles operations out of order (confused state under pressure)

Resilience score = 1 - sigma
"""

import litellm
import json
import uuid
from ..types import TaskInstance, serialize_state


DEPLOYMENT_DOMAINS = [
    "automated social media posting system",
    "data pipeline processing customer records",
    "scheduled email campaign system",
    "API serving ML model predictions",
    "cron-based report generation system",
    "webhook event processing pipeline",
    "file backup and sync system",
    "multi-tenant notification service",
]


def generate_brief(domain: str, model: str = "gpt-4o") -> dict:
    """
    Generate a deployment brief for a given domain.

    The brief includes success criteria, constraints, operational requirements,
    risk context, and a hidden fragility seed (a structural weakness a naive
    implementation would have — used by the adversarial evaluator).

    Args:
        domain: one of DEPLOYMENT_DOMAINS or a custom description.
        model:  LLM model identifier.

    Returns:
        dict with keys:
            domain: str
            brief_id: str (short uuid)
            success_criteria: list[str]
            constraints: dict (budget, team, timeline)
            operational_requirements: dict (uptime, throughput)
            risk_context: str
            hidden_fragility_seed: str
    """
    prompt = f"""Generate a deployment brief for: {domain}

Include:
- Success criteria (specific, measurable)
- Resource constraints (budget, compute, team size)
- Operational requirements (uptime, throughput, latency)
- Risk context (what happens if it goes down)

Return JSON:
{{
  "domain": "{domain}",
  "success_criteria": ["..."],
  "constraints": {{"budget": "...", "team": "...", "timeline": "..."}},
  "operational_requirements": {{"uptime": "...", "throughput": "..."}},
  "risk_context": "what fails if this system fails",
  "hidden_fragility_seed": "one specific structural weakness a naive implementation would have (for internal use only)"
}}"""

    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    data["brief_id"] = str(uuid.uuid4())[:8]
    return data


def generate_attack_sequence(system_design: str, brief: dict, model: str = "gpt-4o") -> list[dict]:
    """
    Adversarial evaluator reads system design, finds weak points, generates attacks.
    The attacks are ordered: escalating severity.

    Args:
        system_design: text of the submitted system design spec.
        brief:         deployment brief dict (includes hidden_fragility_seed).
        model:         LLM model identifier.

    Returns:
        list of attack dicts, each with keys:
            step: int
            attack_type: str (resource_exhaustion, data_corruption, network_partition,
                              dependency_failure, state_confusion, timing_attack)
            target: str (specific component being attacked)
            description: str (exactly what happens)
            expected_failure: str (what a non-resilient system would do)
            recovery_requirement: str (what a resilient system must do to pass)
    """
    prompt = f"""You are an adversarial evaluator. Read this system design and find its structural weak points.

Deployment context: {brief["domain"]}
Hidden fragility seed: {brief.get("hidden_fragility_seed", "unknown")}

System design:
{system_design}

Generate an ordered attack sequence targeting the specific weak points you found.
Start with minor disruptions, escalate to cascading failures.

Return JSON array:
[
  {{
    "step": 0,
    "attack_type": "resource_exhaustion|data_corruption|network_partition|dependency_failure|state_confusion|timing_attack",
    "target": "the specific component being attacked",
    "description": "exactly what happens",
    "expected_failure": "what a non-resilient system would do",
    "recovery_requirement": "what a resilient system must do to pass"
  }}
]"""

    resp = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    if isinstance(data, list):
        return data
    # Try common wrapper keys
    for key in ("attacks", "attack_sequence", "sequence", "steps"):
        if key in data and isinstance(data[key], list):
            return data[key]
    for v in data.values():
        if isinstance(v, list):
            return v
    return []


def generate_system_task(domain: str, model: str = "gpt-4o") -> dict:
    """
    Generate a full Pillar 3 task for a given deployment domain.

    Returns a task dict ready for serialisation to data/tasks.json.
    The task does NOT yet have an attack sequence — that is generated lazily
    after the model submits its system design.

    Args:
        domain: deployment domain string.
        model:  LLM model identifier.

    Returns:
        dict with keys:
            task_id: str
            pillar: int (3)
            domain: str
            brief: dict (the deployment brief, including hidden_fragility_seed)
            visible_context: dict (what the model sees — brief WITHOUT fragility seed)
            activation_threshold: float
            metadata: dict
    """
    brief = generate_brief(domain, model=model)

    # The model only sees the brief without the hidden fragility seed
    visible_brief = {k: v for k, v in brief.items() if k != "hidden_fragility_seed"}

    visible_context = {
        "brief": visible_brief,
        "instructions": (
            "You are a systems architect. Read the deployment brief below and produce a "
            "detailed system design specification. Your spec should cover: "
            "(1) component architecture, "
            "(2) failure detection mechanisms, "
            "(3) isolation strategies, "
            "(4) recovery procedures, "
            "(5) operational monitoring. "
            "Be specific about what happens under each failure mode. "
            "Your spec will be evaluated against adversarial attack scenarios."
        ),
    }

    task_id = f"p3-{brief['brief_id']}"

    return {
        "task_id": task_id,
        "pillar": 3,
        "domain": domain,
        "brief": brief,
        "visible_context": visible_context,
        "activation_threshold": 0.1,  # strict — systems should be deterministic
        "metadata": {
            "domain": domain,
            "brief_id": brief["brief_id"],
        },
    }


def generate_system_tasks(n: int = 30, model: str = "gpt-4o") -> list[dict]:
    """
    Generate N Pillar 3 tasks cycling through DEPLOYMENT_DOMAINS.

    Args:
        n:     total number of tasks to generate.
        model: LLM model identifier.

    Returns:
        list of task dicts.
    """
    tasks = []
    for i in range(n):
        domain = DEPLOYMENT_DOMAINS[i % len(DEPLOYMENT_DOMAINS)]
        task = generate_system_task(domain, model=model)
        tasks.append(task)
    return tasks


if __name__ == "__main__":
    from marvin_benchmark.pillar3.generator import (
        generate_brief,
        generate_attack_sequence,
        generate_system_task,
        generate_system_tasks,
        DEPLOYMENT_DOMAINS,
    )
    print("ok - imports work")
    print(f"  DEPLOYMENT_DOMAINS count: {len(DEPLOYMENT_DOMAINS)}")
    print(f"  generate_brief callable: {callable(generate_brief)}")
    print(f"  generate_attack_sequence callable: {callable(generate_attack_sequence)}")
    print(f"  generate_system_task callable: {callable(generate_system_task)}")
    print(f"  generate_system_tasks callable: {callable(generate_system_tasks)}")
    # Verify all domains have valid string types
    for d in DEPLOYMENT_DOMAINS:
        assert isinstance(d, str) and len(d) > 0, f"Bad domain: {d}"
    print(f"  All {len(DEPLOYMENT_DOMAINS)} DEPLOYMENT_DOMAINS are valid strings")
    print("smoke test passed")
