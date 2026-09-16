#!/usr/bin/env python3
"""Assemble courseware.html from transcripts + extracted slides."""
import json
import os

OUT = "courseware.html"


def main():
    tr = json.load(open("transcripts.json", encoding="utf-8"))
    parts = []
    for p in tr["parts"]:
        n = f"{p['n']:02d}"
        mpath = os.path.join("slides", f"part{n}", "manifest.json")
        if not os.path.exists(mpath):
            print(f"!! missing slides for part{n}, skip")
            continue
        slides = json.load(open(mpath, encoding="utf-8"))
        parts.append({
            "n": p["n"], "id": p["id"], "title": p["title"],
            "audio": f"media/audio/part{n}.m4a",
            "duration": p["duration"],
            "slides": [{"i": s["i"], "t": s["t"], "file": "slides/" + s["file"]} for s in slides],
            "paras": [{"t": x["t"], "e": x["e"], "text": x["text"]} for x in p["paras"]],
        })
        print(f"part{n}: {len(slides)} slides, {len(p['paras'])} paras")
    data = {"course": tr["course"], "source": tr["source"], "parts": parts}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    tpl = open("courseware_template.html", encoding="utf-8").read()
    out = tpl.replace("/*__DATA__*/null", payload)
    open(OUT, "w", encoding="utf-8").write(out)
    total = sum(len(p["slides"]) for p in parts)
    print(f"wrote {OUT}: {len(parts)} parts, {total} slides, {len(out)/1024:.0f} KB")


if __name__ == "__main__":
    main()
