#!/usr/bin/env python3
"""Download audio (m4a) and 1080p H.264 video for all CS329A lectures."""
import os
import sys
import time

from pytubefix import YouTube

PLAYLIST = [
    ("6YnLB0XbTnI", "01"), ("-Ggc37xLj_Y", "02"), ("p7TdPUcPoik", "03"),
    ("Lxh9RF5S-K0", "04"), ("Ml_fp9XkB8Y", "05"), ("yVnmHSAy3ck", "06"),
    ("Uni9dqyuuDM", "07"), ("8JAqLnTaZu4", "08"), ("AyO6wyu4DEg", "09"),
]
V_ITAGS = [137, 399, 248, 136, 298, 299]   # prefer 1080p mp4/h264, then av1/vp9, 720p
A_ITAGS = [140, 139]


def pick(streams, itags):
    for it in itags:
        s = streams.get_by_itag(it)
        if s is not None and s.filesize:
            return s, it
    return None, None


def run(vid, part, tries=4):
    ap = f"media/audio/part{part}.m4a"
    vp = f"media/video/part{part}.mp4"
    need_a = not (os.path.exists(ap) and os.path.getsize(ap) > 1_000_000)
    need_v = not (os.path.exists(vp) and os.path.getsize(vp) > 20_000_000)
    if not need_a and not need_v:
        print(f"[skip] part{part}")
        return
    for attempt in range(1, tries + 1):
        try:
            yt = YouTube(f"https://www.youtube.com/watch?v={vid}")
            if need_a:
                s = yt.streams.get_audio_only()
                print(f"[part{part}] audio itag={s.itag} abr={s.abr} "
                      f"{round((s.filesize or 0)/1e6,1)}MB")
                s.download(output_path="media/audio", filename=f"part{part}.m4a")
                need_a = False
            if need_v:
                s, it = pick(yt.streams.filter(only_video=True, file_extension="mp4"), V_ITAGS)
                if s is None:
                    s, it = pick(yt.streams.filter(only_video=True), V_ITAGS)
                print(f"[part{part}] video itag={it} res={s.resolution} "
                      f"{round((s.filesize or 0)/1e6,1)}MB")
                s.download(output_path="media/video", filename=f"part{part}.mp4")
                need_v = False
            print(f"[ok] part{part}")
            return
        except Exception as e:
            print(f"[retry {attempt}] part{part}: {type(e).__name__} {e}")
            time.sleep(5 * attempt)
    raise SystemExit(f"failed part{part}")


if __name__ == "__main__":
    os.makedirs("media/audio", exist_ok=True)
    os.makedirs("media/video", exist_ok=True)
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for vid, part in PLAYLIST:
        if only and part not in only:
            continue
        run(vid, part)
    print("done")
