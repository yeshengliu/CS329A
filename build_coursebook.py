#!/usr/bin/env python3
"""Build the bilingual (zh/en) illustrated coursebook.

Per lecture: the ELI5 explainer split into sections, each section paired with
the slide frames whose timestamps fall inside it. Duplicate slides (e.g. the
same page captured once from the room camera and once as a screen-share) are
collapsed using the OCR text of each frame. Emits:
  - coursebook.html      (bilingual, default zh)
  - coursebook.zh.html   (bilingual, default zh)
  - coursebook.en.html   (bilingual, default en)
"""
import json
import os
import re

import cv2
import numpy as np

OCR_FILE = "slide_ocr.tsv"
OUT_DIR = os.environ.get("CS329A_OUT", ".")
WEB = os.environ.get("CS329A_WEB", "") == "1"
COURSEWARE_LINK = ('        <a class="pill" href="courseware.html#p${part.n}" '
                   'target="_blank" rel="noopener">${T(\'listen\')} ↗</a>\n')
MIN_WORDS = 3
DEDUP_JACCARD = 0.55       # word-set IoU above which two frames are the same slide
DEDUP_CONTAIN = 0.85       # or this fraction of the smaller frame's words contained
DEDUP_TITLE = 0.5          # same title + this containment -> same slide (progressive reveal)
DEDUP_TITLE_CONTAIN = 0.45
MAX_FIGS_PER_SEC = 10

STOP = set(
    "the a an of to in is are and or for we you it this that with on by as be can "
    "will from at so if not but our their they have has use using more than into out "
    "up down over also such only just its".split()
)


def load_ocr():
    ocr = {}
    if os.path.exists(OCR_FILE):
        for line in open(OCR_FILE, encoding="utf-8"):
            if "\t" in line:
                k, v = line.rstrip("\n").split("\t", 1)
                ocr[k] = v
    return ocr


OCR = load_ocr()


def words(text):
    return {w for w in re.findall(r"[a-z0-9@]+", text.lower()) if w not in STOP and len(w) > 1}


def title_words(text):
    ws = [w for w in re.findall(r"[a-z0-9@]+", text.lower()) if w not in STOP]
    return set(ws[:6])


def jaccard(a, b):
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def contain(a, b):
    m = min(len(a), len(b))
    return len(a & b) / m if m else 0.0


def sharpness(path):
    img = cv2.imread(path)
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def person_frac(path):
    """Fraction of skin-tone pixels: high when a speaker stands in frame."""
    img = cv2.imread(path)
    if img is None:
        return 0.0
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    cr, cb = ycc[..., 1], ycc[..., 2]
    return float(((cr > 133) & (cr < 180) & (cb > 77) & (cb < 130)).mean())


def clean_slides(n):
    """Keep one representative per unique slide page (deduped by OCR text)."""
    mpath = os.path.join("slides", f"part{n:02d}", "manifest.json")
    if not os.path.exists(mpath):
        return []
    man = json.load(open(mpath, encoding="utf-8"))
    reps = []
    for s in man:
        txt = OCR.get("slides/" + s["file"], "")
        w = words(txt)
        if len(w) < MIN_WORDS:
            continue
        ti = title_words(txt)
        path = os.path.join("slides", s["file"])
        sh = sharpness(path)
        person = person_frac(path) > 0.22
        # person frames (speaker in shot) are matched more leniently so they
        # collapse onto the clean capture of the same page
        tj = 0.40 if person else DEDUP_JACCARD
        tc = 0.60 if person else DEDUP_CONTAIN
        tt = 0.35 if person else DEDUP_TITLE_CONTAIN
        hit = None
        for k, r in enumerate(reps):
            if (jaccard(w, r["w"]) >= tj
                    or contain(w, r["w"]) >= tc
                    or (jaccard(ti, r["ti"]) >= DEDUP_TITLE and contain(w, r["w"]) >= tt)):
                hit = k
                break
        if hit is None:
            reps.append({"w": w, "ti": ti, "sharp": sh, "person": person,
                         "t": s["t"], "file": s["file"]})
        else:
            r = reps[hit]
            better = (r["person"] and not person) or \
                     (r["person"] == person and (len(w), sh) > (len(r["w"]), r["sharp"]))
            if better:
                r.update(w=w, sharp=sh, file=s["file"], person=person)
            r["t"] = min(r["t"], s["t"])
    reps.sort(key=lambda r: r["t"])
    return [{"t": r["t"], "file": "slides/" + r["file"]} for r in reps]


def build_part(n, meta):
    en = json.load(open(f"explainers/part{n:02d}.json", encoding="utf-8"))
    zh = json.load(open(f"explainers/part{n:02d}.zh.json", encoding="utf-8"))
    slides = clean_slides(n)
    secs = []

    def pack(x):
        return {"title": x["title"], "problem": x["problem"], "why": x["why"],
                "how": x["how"], "detail": x["detail"], "terms": x["terms"]}

    for i, (se, sz) in enumerate(zip(en["sections"], zh["sections"])):
        t0 = se["t"]
        t1 = en["sections"][i + 1]["t"] if i + 1 < len(en["sections"]) else 10 ** 9
        figs = [x for x in slides if t0 - 1 <= x["t"] < t1]
        if len(figs) > MAX_FIGS_PER_SEC:
            step = len(figs) / MAX_FIGS_PER_SEC
            figs = [figs[int(k * step)] for k in range(MAX_FIGS_PER_SEC)]
        secs.append({
            "t": t0, "figs": figs,
            "en": pack(se), "zh": pack(sz),
        })
    printed = sum(len(s["figs"]) for s in secs)
    print(f"part{n:02d}: {len(secs)} sections, {len(slides)} slides -> {printed} figures")
    return {
        "n": n, "id": meta["id"], "duration": meta["duration"], "slideCount": len(slides),
        "en": {"title": en["title"], "summary": en["summary"]},
        "zh": {"title": zh["title"], "summary": zh["summary"]},
        "sections": secs,
    }


def main():
    tr = json.load(open("transcripts.json", encoding="utf-8"))
    meta = {p["n"]: p for p in tr["parts"]}
    parts = [build_part(n, meta[n]) for n in range(1, 10)]
    data = {"course": tr["course"], "source": tr["source"], "parts": parts}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = open("coursebook_template.html", encoding="utf-8").read()
    for out, lang in (("coursebook.html", "zh"), ("coursebook.zh.html", "zh"), ("coursebook.en.html", "en")):
        html = tpl.replace("/*__DATA__*/null", payload).replace('/*__LANG__*/"zh"', f'"{lang}"')
        if WEB:
            html = html.replace(COURSEWARE_LINK, "")
        open(os.path.join(OUT_DIR, out), "w", encoding="utf-8").write(html)
    total = sum(len(s["figs"]) for p in parts for s in p["sections"])
    print(f"wrote coursebook.html / .zh.html / .en.html — {total} figures")


if __name__ == "__main__":
    main()
