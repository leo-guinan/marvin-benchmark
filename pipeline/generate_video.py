#!/usr/bin/env python3
"""
Kling 3.0 async — fire all predictions simultaneously, poll until done.

Usage:
    export REPLICATE_API_TOKEN=your_token
    python pipeline/generate_video.py
"""
import os, replicate, time, ssl, urllib.request, subprocess

OUT = os.path.expanduser("~/clawd/demis-film/generated")
os.makedirs(OUT, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Define shots: (output_name, prompt)
shots = [
    ("shot1_tnp",
     "cinematic scientific visualization, dark void space, scattered luminescent blue nodes "
     "floating randomly with no connections, each pulsing independently at different rhythms, "
     "chaotic entropic motion, 4K cinematic dark background, slow camera drift"),

    ("shot2_transition",
     "cinematic scientific visualization, dark void space, one central node ignites gold, "
     "waves of light propagate outward through network of blue nodes, "
     "each node transforms blue to gold with connecting threads, "
     "cascade spreading radially, 4K cinematic"),

    ("shot3_tp",
     "cinematic scientific visualization, dark void space, full network of gold nodes "
     "in perfect geometric formation, thin light threads connect all nodes, "
     "stable crystalline equilibrium, camera pulls back revealing full ordered structure, "
     "4K cinematic abstract"),
]

def fire_predictions(shots):
    predictions = {}
    for name, prompt in shots:
        pred = replicate.predictions.create(
            model="kwaivgi/kling-v3-video",
            input={
                "prompt": prompt,
                "duration": 5,
                "aspect_ratio": "16:9",
                "mode": "standard",
                "cfg_scale": 0.5,
            }
        )
        predictions[pred.id] = name
        print(f"  Started {name}: {pred.id}")
    return predictions

def poll_and_download(predictions):
    t0 = time.time()
    completed = {}
    while len(completed) < len(predictions):
        time.sleep(15)
        elapsed = time.time() - t0
        for pred_id, name in predictions.items():
            if pred_id in completed:
                continue
            pred = replicate.predictions.get(pred_id)
            print(f"  {elapsed:.0f}s [{name}] {pred.status}")
            if pred.status == "succeeded":
                url = pred.output if isinstance(pred.output, str) else pred.output[0]
                path = f"{OUT}/{name}.mp4"
                with urllib.request.urlopen(url, context=ctx) as r:
                    data = r.read()
                with open(path, "wb") as f:
                    f.write(data)
                print(f"  SAVED {name}: {len(data)//1024}KB")
                completed[pred_id] = path
            elif pred.status in ("failed", "canceled"):
                print(f"  FAILED {name}: {pred.error}")
                completed[pred_id] = None
    return completed

def concat_shots(names, out_path):
    concat_txt = f"{OUT}/concat.txt"
    with open(concat_txt, "w") as f:
        for name in names:
            f.write(f"file '{OUT}/{name}.mp4'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an", out_path
    ], check=True)
    print(f"Visualization: {out_path}")

if __name__ == "__main__":
    print(f"Generating {len(shots)} shots in parallel...\n")
    predictions = fire_predictions(shots)
    results = poll_and_download(predictions)

    succeeded = [n for _, n in predictions.items() if results.get(_)]
    print(f"\n{len(succeeded)}/{len(shots)} succeeded")

    if len(succeeded) == len(shots):
        names = [name for _, name in shots]
        concat_shots(names, f"{OUT}/visualization.mp4")
