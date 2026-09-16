#!/usr/bin/env python3
"""OCR slide images with the macOS Vision framework (no external binaries)."""
import glob
import json
import os
import sys
import time

import Vision
import Quartz
from Foundation import NSURL


def ocr_one(path):
    url = NSURL.fileURLWithPath_(path)
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    if src is None:
        return ""
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    if cg is None:
        return ""
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(0)          # 0 = accurate
    req.setUsesLanguageCorrection_(False)
    req.setRecognitionLanguages_(["en-US"])
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    handler.performRequests_error_([req], None)
    res = req.results() or []
    return " ".join((c.topCandidates_(1)[0].string() or "") for c in res)


def main():
    paths = []
    for n in range(1, 10):
        for p in sorted(glob.glob(f"slides/part{n:02d}/*.jpg")):
            paths.append(p)
    out = sys.argv[1] if len(sys.argv) > 1 else "slide_ocr.tsv"
    data = {}
    if os.path.exists(out):
        for line in open(out, encoding="utf-8"):
            if "\t" in line:
                k, v = line.rstrip("\n").split("\t", 1)
                data[k] = v
    todo = [p for p in paths if p not in data]
    print(f"{len(paths)} slides, {len(todo)} to OCR")
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        data[p] = ocr_one(p)
        if i % 50 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"  {i}/{len(todo)}  {el:.0f}s  ({el/i:.2f}s each)")
    with open(out, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"{p}\t{data.get(p,'')}\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
