# CS329A · Self-Improving AI Agents — Illustrated Notes

An automatically generated, figure-forward study document for Stanford Online's
**CS329A Self-Improving AI Agents** (Fall 2025) lecture series.

**Live site:** https://yeshengliu.github.io/CS329A/

## What's here

| Path | Description |
|---|---|
| `docs/` | The published static site (GitHub Pages) |
| `docs/coursebook.html` | Illustrated notes, Chinese (default) |
| `docs/coursebook.en.html` | Illustrated notes, English |
| `docs/cs329a.html` | Full-text searchable transcript document |
| `docs/slides/` | Slide frames extracted from the lecture videos |
| `explainers/` | Source notes per lecture (`partNN.json` EN, `partNN.zh.json` ZH) |
| `subtitles/` | Auto-generated English captions (`.srt`) |
| `tools/` | Helper scripts |

## About the notes

Each lecture is split into sections that follow the talk's **real topic
boundaries** (one section per paper / method / experiment / discussion turn),
and every section is written as a **Problem → Why → How** logic chain followed
by a deeper `detail` passage. The audience is an experienced AI-agent engineer,
so terminology is kept intact and the focus is on mechanisms, trade-offs and
edge cases. Each section is paired with the slides shown during its time range.

## Pipeline

```
fetch_subs.py        # download captions (pytubefix)
fetch_media.py       # download audio + 1080p video (kept locally, not published)
slidepipe.py         # detect the projected screen, perspective-correct it, extract slide frames
tools/ocr_slides.py  # OCR every frame with the macOS Vision framework
build_coursebook.py  # dedupe slides by OCR text, attach them to sections, render HTML
build_doc.py         # build cs329a.html (transcript reader)
```

Rebuild the site:

```bash
python3 tools/ocr_slides.py            # writes slide_ocr.tsv
CS329A_OUT=docs CS329A_WEB=1 python3 build_coursebook.py
```

## Credits & usage

Lecture content and slides belong to the course instructors (Stanford Online).
Slides were extracted from the public course videos and are included here for
personal study only. Source playlist:
https://www.youtube.com/playlist?list=PLangBM27OtEA
