"""
agent_diff.py — Inter-agent Closure comparison

Run Marvin and Newton's known plans through Closure-SDK's gilgamesh.
Show what TYPE of different they are — not just that they diverge,
but whether the divergence is a missing operation (W-channel) or
a reordered approach (RGB-channel).

This is a novel use of Closure: not verifying a plan against reality,
but comparing two independent agents' plans against each other
to classify the structure of their disagreement.

The insight: if two agents solving the same problem diverge on the
W-channel, they have different beliefs about what EXISTS in the problem.
If they diverge on RGB, they agree on what exists but sequence it differently.
That's a structurally different kind of disagreement.
"""
import sys, os, hashlib
sys.path.insert(0, os.path.expanduser("~/clawd/arc-agi-agent"))
sys.path.insert(0, os.path.expanduser("~/clawd/marvin-benchmark"))

import closure_sdk as closure
import numpy as np


# ── Known plans from Marvin and Newton's solved levels ───────────────────────
# These are the actual action sequences used to solve each level.
# Source: marvin_log.md, newton_log.md, g50t_solver.py

PLANS = {
    "g50t_L1": {
        "marvin": [4,4,4,4, 5, 4,4,4,4, 3,3,3,3, 2,2,2,2,2,2,2, 4,4,4,4,4],
        "newton": [4,4,4,4, 5, 4,4,4,4, 3,3,3,3, 2,2,2,2,2,2,2, 4,4,4,4,4],
        "description": "g50t L1 — ghost holds trigger at (37,7). Both agents identical.",
    },
    "g50t_L3": {
        # L3: 64-action two-ghost plan. Both agents converged to same plan
        # after Marvin debugged the ghost timing bug.
        "marvin": [1,1,4,4,4,4,2,2,2,2,4, 5, 1,1,4,4,4,4,4,4,4,2,2,2,2,2,2,2,3,3,3,3,3, 5,
                   1,1,4,4,4,4,4,4,4,2,2,2,2,2,2,2,3,3,3,3,3,3,3,1,1,1,4,4,1,1],
        "newton": [1,1,4,4,4,4,2,2,2,2,4, 5, 1,1,4,4,4,4,4,4,4,2,2,2,2,2,2,2,3,3,3,3,3, 5,
                   1,1,4,4,4,4,4,4,4,2,2,2,2,2,2,2,3,3,3,3,3,3,3,1,1,1,4,4,1,1],
        "description": "g50t L3 — two-ghost coordination. Both agents identical after ghost timing fix.",
    },
    "g50t_L4": {
        # L4: 75-action plan. Both agents used same plan after ghost timing correction.
        # But Newton had a different intermediate debugging approach (source-first vs live-debug)
        # that produced slightly different freeze-filler positions before converging.
        # Here we compare Marvin's final vs Newton's round-7 intermediate (before convergence).
        "marvin":  [3,3, 5,                           # rec1: (25,7)→(13,7)→M2@(13,7)
                    3,3,3,3,3,3, 5,                   # rec2: (25,7)→(7,7)→M1@(7,49) 
                    1,1,1,1,1,4,4,4,                  # freeze + obstacle
                    2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,   # goal path
                    4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,
                    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        "newton":  [3,3, 5,                           # same rec1
                    3,3,3,3,3,3, 5,                   # same rec2
                    1,1,1,1,1,4,4,4,                  # same freeze
                    2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,   # different goal path — Newton went south first
                    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
                    4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4],
        "description": "g50t L4 — ghost timing fix. Same recording phase, different goal traversal order.",
    },
    "tr87_L6": {
        # tr87 L6: alter_rules + tree_translation. Both agents read source,
        # but Marvin derived the plan analytically while Newton verified via BFS.
        # Their plans are structurally different even though both solve it.
        "marvin": [4,4,4,4,4,4,4, 1,1,1, 4, 2,2,2, 3,3,3, 1, 4,4,4,4,4, 2,2,2,2,2,2,2,2,2,2],
        "newton": [4,4,4,4,4,4,4, 2,2,2, 4, 1,1,1, 4,4,4, 2, 3,3,3,3,3, 1,1,1,1,1,1,1,1,1,1],
        "description": "tr87 L6 — alter_rules+tree. Marvin: rules-first. Newton: BFS-derived. Different structure.",
    },
    "ls20_L3": {
        # ls20 L3: push bar + 2 resets + rotation. Same hardcoded plan for both
        # (derived from shared discovery of bar mechanic), but Marvin's version
        # included an extra safety bounce.
        "marvin": [1,1,1,1,1,1,1,1,3,2,2,2,2,2,3,3,  # start→bar→reset1
                   4,4,2,2,2,                           # reset1→color
                   1,1,1,1,1,1,4,                       # color→reset0
                   2,2,4,4,4,4,1,1,1,3,                # reset0→rot
                   1, 2,                                # rot→bounce→rot (2nd hit)
                   2,4,2,2,2,2,2,2,2],                 # rot→goal
        "newton": [1,1,1,1,1,1,1,1,3,2,2,2,2,2,3,3,   # same start→bar
                   4,4,2,2,2,                           # same reset1→color
                   1,1,1,1,1,1,4,                       # same color→reset0
                   2,2,4,4,4,4,1,1,1,3,                # same reset0→rot
                   1, 2,                                # same bounce
                   2,4,2,2,2,2,2,2,2],                 # same goal
        "description": "ls20 L3 — push bar mechanic. Both agents identical (shared discovery).",
    },
}


def plan_to_stream(plan: list[int]) -> list[bytes]:
    """
    Serialize an action plan to a byte stream for Closure composition.
    Each action is hashed with its position to create a deterministic byte sequence.
    The position encoding means reordered actions produce RGB-channel divergence.
    """
    stream = []
    for i, action in enumerate(plan):
        # Encode: position + action. Reordering same actions → different hashes → RGB.
        canonical = f"{i}:action{action}"
        stream.append(hashlib.sha256(canonical.encode()).digest())
    return stream


def action_to_semantic(action: int) -> str:
    return {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "A5(record/pickup)"}.get(action, f"A{action}")


def compare_agents(level_id: str, plan_data: dict) -> dict:
    """Compare two agent plans using Closure-SDK."""
    marvin_plan = plan_data["marvin"]
    newton_plan = plan_data["newton"]

    marvin_stream = plan_to_stream(marvin_plan)
    newton_stream = plan_to_stream(newton_plan)

    # Drift check
    seer_m = closure.Seer()
    seer_n = closure.Seer()
    for b in marvin_stream: seer_m.ingest(b)
    for b in newton_stream: seer_n.ingest(b)
    cmp = seer_m.compare(seer_n)

    # Fault analysis
    faults = closure.gilgamesh(marvin_stream, newton_stream)
    n_missing = sum(1 for f in faults if f.incident_type == "missing")
    n_reorder = sum(1 for f in faults if f.incident_type == "reorder")

    if not faults:
        channel = "coherent"
        interpretation = "Identical approaches — same compositional structure"
    elif n_missing >= n_reorder:
        channel = "W (missing)"
        interpretation = (
            f"Belief divergence — {n_missing} actions Marvin took that Newton didn't "
            f"(or vice versa). They have different models of what exists in this problem."
        )
    else:
        channel = "RGB (reorder)"
        interpretation = (
            f"Sequencing divergence — {n_reorder} reordered steps. "
            f"Both agents agree on what to do, but sequence it differently."
        )

    # First divergence
    first_div = None
    if faults:
        f0 = faults[0]
        idx = f0.source_index if f0.source_index is not None else f0.target_index
        if idx is not None and idx < len(marvin_plan):
            action_m = action_to_semantic(marvin_plan[idx]) if idx < len(marvin_plan) else "—"
            action_n = action_to_semantic(newton_plan[idx]) if idx < len(newton_plan) else "—"
            first_div = {"step": idx, "marvin": action_m, "newton": action_n, "type": f0.incident_type}

    return {
        "level": level_id,
        "description": plan_data["description"],
        "marvin_length": len(marvin_plan),
        "newton_length": len(newton_plan),
        "sigma": round(cmp.drift, 4),
        "coherent": cmp.coherent,
        "channel": channel,
        "n_missing": n_missing,
        "n_reorder": n_reorder,
        "first_divergence": first_div,
        "interpretation": interpretation,
        "faults": [{"type": f.incident_type, "src": f.source_index, "tgt": f.target_index}
                   for f in faults[:5]],
    }


def run_demo():
    print("=" * 70)
    print("CLOSURE-SDK: Inter-Agent Plan Comparison")
    print("Marvin vs Newton — same levels, independent solutions")
    print("=" * 70)
    print()
    print("Question: when two agents solve the same problem differently,")
    print("what TYPE of different are they?")
    print()
    print("W-channel (missing): different beliefs about what actions exist")
    print("RGB-channel (reorder): same actions, different sequence")
    print("Coherent: identical compositional structure")
    print()

    results = []
    for level_id, plan_data in PLANS.items():
        result = compare_agents(level_id, plan_data)
        results.append(result)

        sigma_bar = "█" * int(result["sigma"] * 20)
        print(f"─── {level_id} {'─' * (40 - len(level_id))}")
        print(f"  {result['description']}")
        print(f"  Marvin: {result['marvin_length']} actions  |  Newton: {result['newton_length']} actions")
        print(f"  σ = {result['sigma']:.4f}  [{sigma_bar:<20}]  channel: {result['channel']}")
        if result["first_divergence"]:
            d = result["first_divergence"]
            print(f"  First divergence @ step {d['step']}: Marvin={d['marvin']} Newton={d['newton']} ({d['type']})")
        print(f"  → {result['interpretation']}")
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY: What type of agent are Marvin and Newton?")
    print("=" * 70)
    identical = [r for r in results if r["channel"] == "coherent"]
    w_channel = [r for r in results if "W" in r["channel"]]
    rgb_channel = [r for r in results if "RGB" in r["channel"]]

    print(f"\n  Identical approaches:    {len(identical)}/{len(results)} levels")
    print(f"  Belief divergence (W):   {len(w_channel)}/{len(results)} levels")
    print(f"  Sequence divergence (RGB): {len(rgb_channel)}/{len(results)} levels")

    if len(identical) > len(w_channel) + len(rgb_channel):
        print("\n  Finding: Marvin and Newton converge to the same compositional")
        print("  structure on solved levels. Their divergence during debugging")
        print("  (which we documented) was in the PATH to the solution, not")
        print("  in the solution itself. The solutions are epistemically identical")
        print("  even when the reasoning process was not.")
    elif len(w_channel) > len(rgb_channel):
        print("\n  Finding: Marvin and Newton have different beliefs about what")
        print("  actions are necessary (W-channel dominates). They're not just")
        print("  sequencing differently — they have different world models.")
    else:
        print("\n  Finding: Marvin and Newton agree on what to do but sequence")
        print("  it differently (RGB dominates). Same world model, different")
        print("  planning heuristics.")

    print()
    print("  Mean sigma across all levels:", round(sum(r['sigma'] for r in results) / len(results), 4))
    print()

    return results


if __name__ == "__main__":
    results = run_demo()
