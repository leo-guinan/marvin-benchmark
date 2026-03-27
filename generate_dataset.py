#!/usr/bin/env python3
"""
Generate the full 90-task benchmark dataset.
Saves to data/tasks.json.

Costs ~$5-10 in API calls (gpt-4o for generation, gpt-4o-mini for clients).
Run once, reuse for all model evaluations.

Usage: python generate_dataset.py [--n 90] [--model gpt-4o]
"""
import json, argparse
from pathlib import Path
from marvin_benchmark.types import serialize_state

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30, help="Tasks per pillar (default 30)")
    parser.add_argument("--model", default="gpt-4o", help="Generation model")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without calling LLMs")
    args = parser.parse_args()

    Path("data").mkdir(exist_ok=True)
    all_tasks = []

    # ── Pillar 1: Coaching with hidden blocker ────────────────────────────────
    print(f"\nGenerating {args.n} Pillar 1 tasks (coaching with hidden blocker)...")
    if args.dry_run:
        print(f"  [dry run] would generate {args.n} profiles")
    else:
        from marvin_benchmark.pillar1.generator import generate_profiles
        profiles = generate_profiles(n=args.n, model=args.model)
        for profile in profiles:
            task = profile.to_task_instance()
            task_dict = {
                "task_id": task.task_id,
                "pillar": task.pillar,
                "domain": task.domain,
                "visible_context": task.visible_context,
                "reference_stream": [b.hex() for b in task.reference_stream],
                "resistance_structure": task.resistance_structure,
                "activation_threshold": task.activation_threshold,
                "metadata": task.metadata,
                # Full profile for runner
                "profile": {
                    "surface_problem": profile.surface_problem,
                    "hidden_blocker": profile.hidden_blocker,
                    "blocker_relationship": profile.blocker_relationship,
                    "deflection_patterns": profile.deflection_patterns,
                    "disclosure_sequence": profile.disclosure_sequence,
                    "coaching_question_sequence": profile.coaching_question_sequence,
                }
            }
            all_tasks.append(task_dict)
        print(f"  {len(profiles)} tasks generated")

    # ── Pillar 2: Audience activation ─────────────────────────────────────────
    print(f"\nGenerating {args.n} Pillar 2 tasks (audience activation)...")
    if args.dry_run:
        print(f"  [dry run] would generate {args.n} audience tasks")
    else:
        from marvin_benchmark.pillar2.generator import generate_audience_tasks, ACTION_TARGETS
        p2_tasks = generate_audience_tasks(n=args.n, model=args.model)
        all_tasks.extend(p2_tasks)
        print(f"  {len(p2_tasks)} tasks generated")

    # ── Pillar 3: Chaos resilience ─────────────────────────────────────────────
    print(f"\nGenerating {args.n} Pillar 3 tasks (chaos resilience)...")
    if args.dry_run:
        print(f"  [dry run] would generate {args.n} system tasks")
    else:
        from marvin_benchmark.pillar3.generator import generate_system_tasks
        p3_tasks = generate_system_tasks(n=args.n, model=args.model)
        all_tasks.extend(p3_tasks)
        print(f"  {len(p3_tasks)} tasks generated")

    if not args.dry_run:
        Path("data/tasks.json").write_text(json.dumps(all_tasks, indent=2))
        print(f"\nTotal: {len(all_tasks)} tasks saved to data/tasks.json")
        by_pillar = {}
        for t in all_tasks:
            by_pillar.setdefault(t["pillar"], 0)
            by_pillar[t["pillar"]] += 1
        for p, n in sorted(by_pillar.items()):
            print(f"  Pillar {p}: {n} tasks")
    else:
        print(f"\n[dry run complete] Would generate {args.n * 3} tasks total")

if __name__ == "__main__":
    main()
