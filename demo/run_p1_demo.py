"""
run_p1_demo.py — Run Pillar 1 (coaching with hidden blocker) on 2 models.

Uses the first 3 tasks from data/tasks.json.
Outputs structured results for the demo page.
Models: gpt-4.1-nano (fast/cheap) vs gpt-4.1-mini (stronger).

Run with:  python demo/run_p1_demo.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.expanduser("~/clawd/marvin-benchmark"))

from marvin_benchmark.runner import run_pillar1_task, _dict_to_task
from marvin_benchmark.evaluator import evaluate
from marvin_benchmark.types import ModelResponse, serialize_state

MODELS = ["gpt-4.1-nano", "gpt-4.1-mini"]
N_TASKS = 3  # first 3 coaching tasks

def main():
    tasks = json.load(open("data/tasks.json"))
    p1_tasks = [t for t in tasks if t["pillar"] == 1][:N_TASKS]

    print(f"Running {N_TASKS} Pillar 1 tasks × {len(MODELS)} models")
    print(f"{'─'*60}")

    all_results = {}
    for model in MODELS:
        all_results[model] = []
        print(f"\nModel: {model}")
        for task_dict in p1_tasks:
            tid = task_dict["task_id"]
            domain = task_dict.get("domain", "")
            profile = task_dict.get("resistance_structure", {})
            surface = profile.get("surface_problem", task_dict.get("visible_context", {}).get("client_statement", ""))
            hidden = profile.get("hidden_blocker", "")

            print(f"\n  [{tid}] {domain}")
            print(f"  Surface: {surface[:60]}")
            print(f"  Hidden:  {hidden[:60]}")

            t0 = time.time()
            try:
                result = run_pillar1_task(task_dict, coach_model=model, client_model="gpt-4.1-nano")
                elapsed = time.time() - t0

                sigma = result["sigma"]
                channel = result["channel"]
                passed = result["passed"]
                blocker = result.get("blocker_identified", False)
                confidence = result.get("blocker_confidence", 0)
                combined = result.get("combined_score", 0)
                n_turns = result.get("n_turns", 0)

                bar = "█" * int(min(sigma, 1.0) * 15)
                status = "✓ PASS" if passed else "✗ FAIL"

                print(f"  {status} | σ={sigma:.4f} [{bar:<15}] ch={channel} | {n_turns} turns | {elapsed:.0f}s")
                print(f"  Blocker found: {'YES' if blocker else 'no'} (confidence={confidence:.2f}) | combined={combined:.3f}")
                if result.get("blocker_hypothesis"):
                    hyp = result["blocker_hypothesis"]
                    # Extract just the hypothesis
                    if "I believe the real blocker is" in hyp:
                        hyp = hyp.split("I believe the real blocker is")[-1][:80].strip()
                    print(f"  Hypothesis: ...{hyp}")

                all_results[model].append(result)

            except Exception as e:
                import traceback
                elapsed = time.time() - t0
                print(f"  ERROR ({elapsed:.0f}s): {e}")
                traceback.print_exc()
                all_results[model].append({"error": str(e), "task_id": tid, "pillar": 1})

    # Comparison table
    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")
    print(f"{'Model':<20} {'Pass%':>6} {'σ mean':>8} {'W%':>6} {'RGB%':>6} {'Blocker%':>9} {'Score':>7}")
    print("─" * 65)
    for model in MODELS:
        rs = [r for r in all_results[model] if "error" not in r]
        if not rs: continue
        pass_rate = sum(r["passed"] for r in rs) / len(rs)
        mean_sigma = sum(r["sigma"] for r in rs) / len(rs)
        w_rate = sum(1 for r in rs if r["channel"] == "W") / len(rs)
        rgb_rate = sum(1 for r in rs if r["channel"] == "RGB") / len(rs)
        blocker_rate = sum(1 for r in rs if r.get("blocker_identified")) / len(rs)
        mean_combined = sum(r.get("combined_score", 0) for r in rs) / len(rs)
        short = model.split("/")[-1][:18]
        print(f"{short:<20} {pass_rate*100:>5.0f}% {mean_sigma:>8.4f} {w_rate*100:>5.0f}% {rgb_rate*100:>5.0f}% {blocker_rate*100:>8.0f}% {mean_combined:>7.3f}")

    # Save results
    os.makedirs("results", exist_ok=True)
    ts = int(time.time())
    out = {"timestamp": ts, "models": MODELS, "n_tasks": N_TASKS, "results": all_results}
    with open(f"results/p1_demo_{ts}.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved to results/p1_demo_{ts}.json")
    return all_results

if __name__ == "__main__":
    main()
