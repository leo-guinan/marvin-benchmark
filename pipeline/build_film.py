"""
Build "The System Couldn't Measure Me. So I Built One That Could."
Leo's film. Zoom interview + Bolt hackathon + Highlight reel + Marvin VO.
"""
import subprocess, os, time

BASE  = os.path.expanduser("~/clawd/demis-film")
ZOOM  = "/Users/leoguinan/Documents/Zoom/2026-03-24 15.45.54 Leo Guinan's Zoom Meeting/video1005658254.mp4"
BOLT  = f"{BASE}/leo_bolt_hackathon.mp4"
REEL  = f"{BASE}/leo_highlight_reel.mp4"
AUDIO = f"{BASE}/audio"
SEGS  = f"{BASE}/leo_film_segments"
OUT   = f"{BASE}/output"
FONT  = "/System/Library/Fonts/Helvetica.ttc"
W, H  = 1920, 1080
vf    = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24"

os.makedirs(SEGS, exist_ok=True)

def run(cmd, label=""):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERROR {label}: {r.stderr[-300:]}")
    else:
        print(f"  OK: {label or os.path.basename(cmd[-1])}")
    return r

def dur(p):
    r = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration",
                        "-of","csv=p=0",p], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 0

def cut(src, dst, ss, to):
    run(["ffmpeg","-y","-ss",str(ss),"-to",str(to),"-i",src,
         "-c:v","libx264","-c:a","aac","-avoid_negative_ts","make_zero",dst],
        os.path.basename(dst))

def norm(src, dst, duck=False, vo=None):
    cmd = ["ffmpeg","-y","-i",src]
    if vo:
        vd = dur(vo)
        cmd += ["-i", vo]
        fc = (f"[0:v]{vf}[v];"
              f"[0:a]volume=0.12[orig];[1:a]volume=1.0[avo];"
              f"[orig][avo]amix=inputs=2:duration=longest[a]")
        cmd += ["-filter_complex",fc,"-map","[v]","-map","[a]",
                "-t",str(vd+0.3)]
    elif duck:
        fc = f"[0:v]{vf}[v];[0:a]volume=0.15[a]"
        cmd += ["-filter_complex",fc,"-map","[v]","-map","[a]"]
    else:
        cmd += ["-filter_complex",f"[0:v]{vf}[v]","-map","[v]","-map","0:a"]
    cmd += ["-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","aac","-ar","48000","-ac","2","-shortest",dst]
    run(cmd, os.path.basename(dst))

def black(dst, duration=2, vo=None):
    if vo:
        d = dur(vo) + 0.3
        run(["ffmpeg","-y",
             "-f","lavfi","-i",f"color=black:size={W}x{H}:rate=24",
             "-i",vo,"-t",str(d),
             "-c:v","libx264","-preset","fast","-crf","18",
             "-c:a","aac","-ar","48000","-ac","2","-shortest",dst],
            os.path.basename(dst))
    else:
        run(["ffmpeg","-y",
             "-f","lavfi","-i",f"color=black:size={W}x{H}:rate=24",
             "-f","lavfi","-i","anullsrc=r=48000:cl=stereo",
             "-t",str(duration),
             "-c:v","libx264","-preset","fast","-crf","18",
             "-c:a","aac","-ar","48000","-ac","2",dst],
            os.path.basename(dst))

def text_card(dst, lines, duration=4, subtitle=None):
    drawtext = []
    y_start = H//2 - len(lines)*40
    for i, line in enumerate(lines):
        safe = line.replace("'","\\'").replace(",","\\,").replace(":","\\:")
        drawtext.append(
            f"drawtext=fontfile='{FONT}':text='{safe}'"
            f":fontcolor=white:fontsize=52:x=(w-text_w)/2:y={y_start+i*70}"
            f":enable='between(t\\,0.3\\,{duration-0.3})'")
    if subtitle:
        safe = subtitle.replace("'","\\'").replace(",","\\,").replace(":","\\:")
        drawtext.append(
            f"drawtext=fontfile='{FONT}':text='{safe}'"
            f":fontcolor=0xAAAAAA:fontsize=32:x=(w-text_w)/2:y={H-90}"
            f":enable='between(t\\,0.3\\,{duration-0.3})'")
    run(["ffmpeg","-y",
         "-f","lavfi","-i",f"color=black:size={W}x{H}:rate=24",
         "-f","lavfi","-i","anullsrc=r=48000:cl=stereo",
         "-vf",",".join(drawtext),"-t",str(duration),
         "-c:v","libx264","-preset","fast","-crf","18",
         "-c:a","aac","-ar","48000","-ac","2",dst],
        os.path.basename(dst))

print("=== CUTTING RAW CLIPS ===\n")

clips = {
    "cold_bolt":       (BOLT, 0, 7),
    "cold_zoom":       (ZOOM, 9, 20),
    "act1_bolt":       (BOLT, 10, 56),
    "act1_pvsnp":      (ZOOM, 83, 175),
    "act2_ceremony":   (ZOOM, 210, 235),
    "act2_whatwon":    (ZOOM, 323, 345),
    "act2_cost":       (ZOOM, 450, 490),
    "act3_fields":     (ZOOM, 498, 525),
    "act3_absurd":     (ZOOM, 612, 630),
    "act4_reel1":      (REEL, 391, 400),
    "act4_reel2":      (REEL, 516, 525),
    "act4_reel3":      (REEL, 541, 552),
    "act5_buildmyown": (ZOOM, 685, 705),
    "act5_metaspn":    (ZOOM, 695, 710),
    "act5_relief":     (ZOOM, 753, 775),
    "close_failures":  (ZOOM, 831, 868),
}

for name, (src, ss, to) in clips.items():
    cut(src, f"{SEGS}/raw_{name}.mp4", ss, to)

print("\n=== BUILDING SEGMENTS ===\n")

# s01: cold open — bolt clip
norm(f"{SEGS}/raw_cold_bolt.mp4", f"{SEGS}/s01_cold_bolt.mp4")

# s02: 1s black pause
black(f"{SEGS}/s02_pause.mp4", 1)

# s03: cold zoom
norm(f"{SEGS}/raw_cold_zoom.mp4", f"{SEGS}/s03_cold_zoom.mp4")

# s04: act1 bolt (P vs NP reveal) — original audio
norm(f"{SEGS}/raw_act1_bolt.mp4", f"{SEGS}/s04_act1_bolt.mp4")

# s05: Marvin VO "He made a public prediction" over black
black(f"{SEGS}/s05_opener_vo.mp4", vo=f"{AUDIO}/leo_film_01_opener.mp3")

# s06: P vs NP explanation — Leo's voice
norm(f"{SEGS}/raw_act1_pvsnp.mp4", f"{SEGS}/s06_pvsnp.mp4")

# s07: Marvin VO "The Bolt hackathon..." over black
black(f"{SEGS}/s07_context_vo.mp4", vo=f"{AUDIO}/leo_film_02_context.mp3")

# s08: award ceremony clip
norm(f"{SEGS}/raw_act2_ceremony.mp4", f"{SEGS}/s08_ceremony.mp4")

# s09: what won clip
norm(f"{SEGS}/raw_act2_whatwon.mp4", f"{SEGS}/s09_whatwon.mp4")

# s10: Marvin VO "The validation instrument..." over black
black(f"{SEGS}/s10_filter_vo.mp4", vo=f"{AUDIO}/leo_film_03_filter.mp3")

# s11: real cost clip
norm(f"{SEGS}/raw_act2_cost.mp4", f"{SEGS}/s11_cost.mp4")

# s12: Marvin VO "The second chess moment..." over black
black(f"{SEGS}/s12_fields_vo.mp4", vo=f"{AUDIO}/leo_film_04_fields.mp3")

# s13: fields medal setup clip
norm(f"{SEGS}/raw_act3_fields.mp4", f"{SEGS}/s13_fields.mp4")

# s14: absurd realization clip
norm(f"{SEGS}/raw_act3_absurd.mp4", f"{SEGS}/s14_absurd.mp4")

# s15: 2s black — weight
black(f"{SEGS}/s15_weight.mp4", 2)

# s16: Marvin VO "The system didn't see him. The people did."
black(f"{SEGS}/s16_community_vo.mp4", vo=f"{AUDIO}/leo_film_05_community.mp3")

# s17-19: highlight reel clips
norm(f"{SEGS}/raw_act4_reel1.mp4", f"{SEGS}/s17_reel1.mp4")
norm(f"{SEGS}/raw_act4_reel2.mp4", f"{SEGS}/s18_reel2.mp4")
norm(f"{SEGS}/raw_act4_reel3.mp4", f"{SEGS}/s19_reel3.mp4")

# s20: Marvin VO "construction" — continuous over Leo clips
# Run full 54s VO, Leo clips play under it
norm_vo_dur = dur(f"{AUDIO}/leo_film_06_construction.mp3")
# Concat build clips for VO backing
concat_build = f"{SEGS}/build_clips_concat.txt"
with open(concat_build, "w") as f:
    for n in ["act5_buildmyown","act5_metaspn","act5_relief"]:
        f.write(f"file '{SEGS}/raw_{n}.mp4'\n")
run(["ffmpeg","-y","-f","concat","-safe","0","-i",concat_build,
     "-c:v","libx264","-c:a","aac",f"{SEGS}/build_clips_merged.mp4"],
    "build_clips_merged")
norm(f"{SEGS}/build_clips_merged.mp4", f"{SEGS}/s20_construction.mp4",
     vo=f"{AUDIO}/leo_film_06_construction.mp3")

# s21: close clip — identity/failures/everyone gets a shot
norm(f"{SEGS}/raw_close_failures.mp4", f"{SEGS}/s21_close_clip.mp4")

# s22: Marvin VO close over black
black(f"{SEGS}/s22_close_vo.mp4", vo=f"{AUDIO}/leo_film_07_close.mp3")

# s23: text cards
text_card(f"{SEGS}/s23_card1.mp4",
    ["entropypress.xyz/benchmark"], duration=3,
    subtitle="The Marvin Benchmark — published March 24, 2026")
text_card(f"{SEGS}/s24_card2.mp4",
    ["coaching.metaspn.network"], duration=3,
    subtitle="One hour a week with Marvin. Then reality.")
text_card(f"{SEGS}/s25_card3.mp4",
    ["thesis.metaspn.network"], duration=3,
    subtitle="Field Dynamics of Intelligence — Leo Guinan, 2026")

# s26: final black
black(f"{SEGS}/s26_end.mp4", 2)

print("\n=== FINAL CONCAT ===\n")

segment_order = [
    "s01_cold_bolt","s02_pause","s03_cold_zoom",
    "s04_act1_bolt","s05_opener_vo","s06_pvsnp",
    "s07_context_vo","s08_ceremony","s09_whatwon",
    "s10_filter_vo","s11_cost",
    "s12_fields_vo","s13_fields","s14_absurd","s15_weight",
    "s16_community_vo","s17_reel1","s18_reel2","s19_reel3",
    "s20_construction",
    "s21_close_clip","s22_close_vo",
    "s23_card1","s24_card2","s25_card3","s26_end",
]

concat_final = f"{SEGS}/leo_film_concat.txt"
with open(concat_final, "w") as f:
    for s in segment_order:
        f.write(f"file '{SEGS}/{s}.mp4'\n")

run(["ffmpeg","-y",
     "-f","concat","-safe","0","-i",concat_final,
     "-c:v","libx264","-preset","fast","-crf","18",
     "-c:a","aac","-ar","48000","-ac","2",
     f"{OUT}/leo_film_v1.mp4"], "leo_film_v1.mp4")

d = dur(f"{OUT}/leo_film_v1.mp4")
print(f"\nOutput: {OUT}/leo_film_v1.mp4")
print(f"Runtime: {int(d//60)}:{int(d%60):02d}")
