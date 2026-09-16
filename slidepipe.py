#!/usr/bin/env python3
"""Extract slide images from classroom-camera lecture videos.

Pipeline per video:
  1. Decode at 1 fps, detect the projected-screen quadrilateral each frame.
  2. Warp the screen region to a canonical 16:9 thumbnail; hash it.
  3. Group consecutive frames into stable "slide runs".
  4. For each run pick a representative frame (closest to the run's temporal
     median -> avoids a speaker occluding the slide) and warp it at full res.
  5. Dedupe and write slides + manifest.json.
"""
import glob
import json
import os
import subprocess
import sys

import cv2
import numpy as np

WARP_W, WARP_H = 1600, 900


def order_quad(q):
    q = np.array(q, dtype=np.float32)
    s = q.sum(1)
    d = np.diff(q, axis=1).reshape(-1)
    tl = q[np.argmin(s)]
    br = q[np.argmax(s)]
    tr = q[np.argmin(d)]
    bl = q[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def detect_screen(img):
    """Return ('screen', quad) or ('full', None) or (None, None)."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    V = hsv[..., 2]
    bright = (V > 140).astype(np.uint8) * 255
    if bright.mean() > 255 * 0.78:
        return "full", None
    k = max(9, int(round(w * 0.02)) | 1)
    mask = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:4]:
        a = cv2.contourArea(c) / (w * h)
        if not (0.12 < a < 0.80):
            continue
        ap = cv2.approxPolyDP(c, 0.03 * cv2.arcLength(c, True), True)
        if len(ap) != 4:
            continue
        q = order_quad(ap.reshape(4, 2))
        ww = np.linalg.norm(q[1] - q[0])
        hh = np.linalg.norm(q[3] - q[0])
        if hh < 1:
            continue
        ar = ww / hh
        if not (1.15 < ar < 2.3):
            continue
        return "screen", q
    return None, None


def warp(img, kind, quad):
    h, w = img.shape[:2]
    if kind == "full":
        crop = img[int(h * 0.06):, :]
        return cv2.resize(crop, (WARP_W, WARP_H), interpolation=cv2.INTER_AREA)
    dst = np.array([[0, 0], [WARP_W - 1, 0], [WARP_W - 1, WARP_H - 1], [0, WARP_H - 1]],
                   dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, M, (WARP_W, WARP_H))


def dhash(img, size=8):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (size + 1, size), interpolation=cv2.INTER_AREA)
    return (g[:, 1:] > g[:, :-1]).flatten()


def ham(a, b):
    return int(np.count_nonzero(a != b))


def read_frames(video, fps=1, width=480):
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps},scale={width}:-2",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10 ** 8)
    w, h = width, width * 9 // 16
    n = 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        yield n, np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
        n += 1
    p.stdout.close()
    p.wait()


def grab_full(video, t, kind_hint=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", video, "-frames:v", "1",
           "-f", "image2pipe", "-vcodec", "png", "-"]
    out = subprocess.run(cmd, capture_output=True).stdout
    if not out:
        return None, None, None
    img = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None, None, None
    kind, quad = detect_screen(img)
    if kind is None:
        return None, None, None
    return img, kind, quad


def process(video, part, outroot="slides", change=6, min_run=2, verbose=True):
    outdir = os.path.join(outroot, f"part{part}")
    os.makedirs(outdir, exist_ok=True)
    timeline = []          # (t, kind, quad, thumb_small, hash)
    for n, img in read_frames(video):
        kind, quad = detect_screen(img)
        if kind is None:
            timeline.append((n, None, None, None, None))
            continue
        wimg = warp(img, kind, quad)
        small = cv2.resize(wimg, (160, 90), interpolation=cv2.INTER_AREA)
        timeline.append((n, kind, quad, small, dhash(small)))

    runs = []
    cur = []
    for e in timeline:
        t, kind, quad, small, h = e
        if kind is None:
            if cur:
                runs.append(cur)
                cur = []
            continue
        if not cur:
            cur = [e]
            continue
        prev = cur[-1]
        if ham(prev[4], h) <= change:
            cur.append(e)
        else:
            runs.append(cur)
            cur = [e]
    if cur:
        runs.append(cur)

    kept, prev_hash = [], None
    for run in runs:
        if len(run) < min_run:
            continue
        smalls = np.stack([r[3].astype(np.float32) for r in run])
        med = np.median(smalls, axis=0).astype(np.uint8)
        best = min(run, key=lambda r: float(np.mean((r[3].astype(np.float32) - med) ** 2)))
        t = best[0]
        img, kind, quad = grab_full(video, t)
        if img is None:
            continue
        full = warp(img, kind, quad)
        fh = dhash(full)
        if prev_hash is not None and ham(prev_hash, fh) < change + 2:
            continue
        prev_hash = fh
        kept.append((t, full))
        if verbose and len(kept) % 10 == 0:
            print(f"  ...{len(kept)} slides at {t}s")

    manifest = []
    for i, (t, full) in enumerate(kept, 1):
        name = f"slide_{i:03d}.jpg"
        cv2.imwrite(os.path.join(outdir, name), full, [cv2.IMWRITE_JPEG_QUALITY, 85])
        manifest.append({"i": i, "t": round(t, 2), "file": f"part{part}/{name}"})
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


if __name__ == "__main__":
    video, part = sys.argv[1], sys.argv[2]
    thr = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    m = process(video, part, change=thr)
    print(f"part {part}: {len(m)} slides")
    for x in m[:6]:
        print("  ", x["t"], x["file"])
