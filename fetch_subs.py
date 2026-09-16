import os
import re
import json
import time
from pytubefix import YouTube

PLAYLIST = [
    ("6YnLB0XbTnI", "01", "Course Overview"),
    ("-Ggc37xLj_Y", "02", "Test-Time Compute Scaling"),
    ("p7TdPUcPoik", "03", "Robust Verification"),
    ("Lxh9RF5S-K0", "04", "Learning from Feedback with Tools and Code"),
    ("Ml_fp9XkB8Y", "05", "Planning and Multi-Step Reasoning"),
    ("yVnmHSAy3ck", "06", "Train-Time Scaling and Scaling RL"),
    ("Uni9dqyuuDM", "07", "Self-Improvement and Deep Research Agents"),
    ("8JAqLnTaZu4", "08", "Agentic Evaluations and Long Horizon Tasks"),
    ("AyO6wyu4DEg", "09", "Future Research Areas"),
]

OUT = "subtitles"
os.makedirs(OUT, exist_ok=True)


def clean_title(t):
    return re.sub(r"\|", "", t).strip()


def download(vid, idx, short, tries=4):
    name = f"{idx} - {short}"
    path = os.path.join(OUT, name + ".srt")
    if os.path.exists(path) and os.path.getsize(path) > 2000:
        print(f"[skip] {name}")
        return path
    last = None
    for attempt in range(1, tries + 1):
        try:
            yt = YouTube(f"https://www.youtube.com/watch?v={vid}")
            cap = yt.captions.get("a.en") or next(
                (c for c in yt.captions if c.code.startswith("a.")), None
            )
            if cap is None:
                raise RuntimeError("no auto caption found")
            srt = cap.generate_srt_captions()
            with open(path, "w", encoding="utf-8") as f:
                f.write(srt)
            print(f"[ok] {name} ({len(srt)} bytes)")
            return path
        except Exception as e:
            last = e
            print(f"[retry {attempt}] {name}: {type(e).__name__} {e}")
            time.sleep(4 * attempt)
    raise SystemExit(f"failed {name}: {last}")


def main():
    index = []
    for vid, idx, short in PLAYLIST:
        p = download(vid, idx, short)
        index.append({"id": vid, "part": idx, "title": short, "file": p})
    with open("index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print("done")


if __name__ == "__main__":
    main()
