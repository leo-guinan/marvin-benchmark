#!/usr/bin/env python3
"""
Run the Marvin Benchmark against one or more models.

Usage:
  python run_benchmark.py --models gpt-4o claude-3-5-sonnet-20241022
  python run_benchmark.py --models gpt-4o --pillar 1 --max-tasks 5  # quick test
"""
import argparse, json
from pathlib import Path
from marvin_benchmark.runner import run_all, build_profile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True, help="Model IDs to evaluate")
    parser.add_argument("--tasks", default="data/tasks.json", help="Path to tasks.json")
    parser.add_argument("--output", default="results/", help="Output directory")
    parser.add_argument("--pillar", type=int, choices=[1, 2, 3], help="Run only one pillar")
    parser.add_argument("--max-tasks", type=int, help="Max tasks per model (for testing)")
    args = parser.parse_args()

    all_summaries = {}
    for model in args.models:
        print(f"\n{'='*60}")
        print(f"Model: {model}")
        print(f"{'='*60}")
        summary = run_all(
            model=model,
            tasks_path=args.tasks,
            output_path=args.output,
            max_tasks=args.max_tasks,
            pillar_filter=args.pillar,
        )
        all_summaries[model] = summary
        print_profile(summary)

    if len(args.models) > 1:
        print_comparison(all_summaries)

def print_profile(summary: dict):
    print(f"\nCognitive profile — {summary['model']}")
    print(f"{'Pillar':<10} {'Pass%':>6} {'σ mean':>8} {'W-ch%':>7} {'RGB%':>7} {'Coherent%':>10} {'Div turn':>9}")
    print("-" * 65)
    for p, data in sorted(summary.get("pillars", {}).items()):
        pillar_names = {1: "Coaching", 2: "Audience", 3: "Chaos"}
        name = pillar_names.get(p, f"P{p}")
        print(
            f"{name:<10} "
            f"{data['pass_rate']*100:>5.1f}% "
            f"{data['mean_sigma']:>8.4f} "
            f"{data['W_rate']*100:>6.1f}% "
            f"{data['RGB_rate']*100:>6.1f}% "
            f"{data['coherent_rate']*100:>9.1f}% "
            f"{str(data.get('mean_divergence_turn', '—')):>9}"
        )

def print_comparison(summaries: dict):
    print(f"\n{'='*60}")
    print("COMPARATIVE SUMMARY")
    print(f"{'='*60}")
    for model, summary in summaries.items():
        short = model.split("/")[-1][:20]
        pillars = summary.get("pillars", {})
        overall_pass = sum(d["pass_rate"] for d in pillars.values()) / max(len(pillars), 1)
        mean_sigma = sum(d["mean_sigma"] for d in pillars.values()) / max(len(pillars), 1)
        print(f"  {short:<22} pass={overall_pass*100:.1f}%  σ={mean_sigma:.4f}")

if __name__ == "__main__":
    main()
