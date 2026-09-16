#!/usr/bin/env python3
"""Build a self-contained interactive HTML study document from the CS329A subtitles."""
import glob
import html
import json
import os
import re

OUT_HTML = "cs329a.html"

ACRONYM_STOP = set("""AI OK US AM PM TV ID THE AND FOR NOT YOU BUT CAN ALL ONE TWO NEW SEE USE ITS OUT OUR ANY HAS WAS
ARE HIS HER HAD HOW WHO WHY YES LET NOW GET GOT MAKE MADE INTO OVER SUCH ONLY ALSO EVEN JUST MORE MOST MUCH
MANY SOME LIKE WELL WILL WOULD COULD SHOULD THAN THEN THEM THEY THIS THAT WITH FROM HAVE HERE WHAT WHEN YOUR
VERY BEEN BOTH EACH FEW OWN SAME TOO DOES DID DOING BEING BEEN ABOUT WHILE WHERE WHICH THESE THOSE THERE
MAYBE KIND SORT THING THINGS POINT PART WAY TIME CASE TYPE LOT BIT END SIDE FACE FACT TERM GOOD BAD BIG SMALL
HIGH LOW LONG REAL TRUE FALSE FULL HALF NEXT LAST FIRST SECOND THIRD STATE STORY MODEL MODELS USING BASED""".split())

CONCEPTS = [
    "test-time compute", "inference-time compute", "compute scaling", "scaling law",
    "process reward model", "outcome reward model", "reward model", "reward hacking",
    "chain of thought", "chain-of-thought", "self-consistency", "majority voting",
    "best-of-n", "beam search", "verifier", "verification", "generator",
    "reinforcement learning", "supervised fine-tuning", "fine-tuning", "pretraining",
    "policy gradient", "advantage", "value function", "q-learning", "ppo", "grpo",
    "dpo", "direct preference optimization", "rlhf", "kl divergence", "entropy",
    "monte carlo tree search", "tree search", "search", "planning", "backtracking",
    "reflection", "self-improvement", "self-play", "self-training", "bootstrapping",
    "distillation", "knowledge distillation", "in-context learning", "few-shot",
    "tool use", "function calling", "code execution", "sandbox", "interpreter",
    "agent", "agentic", "multi-agent", "environment", "feedback", "environment reset",
    "world model", "memory", "long-horizon", "long context", "context length",
    "generalization", "memorization", "overfitting", "data contamination",
    "deep research", "retrieval", "rag", "retrieval-augmented generation",
    "embedding", "benchmark", "evaluation", "eval", "rubric", "grader",
    "reasoning", "test case", "unit test", "pass@k", "swe-bench", "aime", "gpqa",
    "math", "proof", "theorem", "lean", "formal verification", "autoformalization",
    "efficiency", "latency", "token budget", "testtime", "test time",
    "task", "trajectory", "rollout", "episode", "steps", "step level", "token level",
    "curriculum", "exploration", "exploitation", "cold start", "warm start",
]

SRT_GLOB = "subtitles/*.srt"


def parse_srt(path):
    text = open(path, encoding="utf-8").read().lstrip("\ufeff")
    segs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        m = re.search(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block
        )
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        body = block[m.end():].strip()
        body = re.sub(r"<[^>]+>", "", body)
        body = " ".join(body.split())
        if body:
            segs.append((round(start, 2), round(end, 2), body))
    return segs


def merge_paragraphs(segs):
    paras = []
    cur = None
    for start, end, txt in segs:
        if cur is None:
            cur = {"t": start, "e": end, "text": txt}
            continue
        prev = cur["text"]
        if txt == prev or prev.endswith(txt) or txt in prev:
            cur["e"] = end
            continue
        gap = start - cur["e"]
        boundary = (
            (gap > 1.3 and re.search(r"[.!?]$", prev))
            or len(prev) > 620
            or (gap > 0.9 and re.match(r"^(So|Now|Okay|OK|Next|Alright|All right|But|And so|Then|Finally)\b", txt))
            and len(prev) > 220
        )
        if boundary:
            paras.append(cur)
            cur = {"t": start, "e": end, "text": txt}
        else:
            joiner = "" if prev.endswith(("—", "-")) else " "
            cur["text"] = prev + joiner + txt
            cur["e"] = end
    if cur:
        paras.append(cur)
    return paras


OUTLINE_RE = re.compile(
    r"\b(the next (thing|topic|part|section|component|piece|step)|"
    r"let'?s (move on|talk about|dive into|discuss|look at|start|go)|"
    r"(now|so|and so|then) (let'?s|we'?ll|i'?ll|we will|i will) (talk|discuss|look|move|see)|"
    r"the first (thing|part|topic|component|step|set)|"
    r"moving on|to summarize|in summary|the key (takeaway|takeaways|point|points|idea|ideas|insight|insights)|"
    r"today (we'?ll|we will|i'?ll|i will|we'?re going to)|"
    r"(overview|roadmap|outline) of (the|this)|"
    r"one (thing|idea|concept) (i|we) (want|wanna)|"
    r"let me (talk about|start|begin)|"
    r"the main (idea|point|takeaway)|"
    r"next (up|slide)|finally\b)",
    re.I,
)


LEAD_RE = re.compile(
    r"^(and then|and so|and|so|now|okay|ok|next|alright|all right|but|uh|um|yeah|"
    r"well|no,? yeah|right|like|i mean|you know|we'?re going to|we will|i want to|"
    r"i wanna|let'?s|the next thing is|first)[,\s]+",
    re.I,
)


def build_outline(paras):
    out = []
    last_t = -999
    for p in paras:
        if not OUTLINE_RE.search(p["text"]):
            continue
        if p["t"] - last_t < 25:
            continue
        label = re.sub(r"\s+", " ", p["text"]).strip()
        prev = None
        while prev != label:
            prev = label
            label = LEAD_RE.sub("", label).strip()
        label = re.sub(r"\b(u+m+|uh+)\b", "", label)
        label = re.sub(r"\s+", " ", label).strip()
        words = label.split(" ")
        label = " ".join(words[:13]) + ("…" if len(words) > 13 else "")
        if len(label) < 12:
            continue
        out.append({"t": p["t"], "label": label})
        last_t = p["t"]
    return out[:30]


def build_glossary(parts):
    full = " ".join(p["text"] for part in parts for p in part["paras"])
    low = full.lower()
    acronyms = {}
    for m in re.finditer(r"\b[A-Z][A-Z0-9]{1,5}\b", full):
        tok = m.group(0)
        if tok in ACRONYM_STOP or tok.isdigit() or tok in {"OM", "PO", "SA", "LMS", "V2", "QA", "RLS", "IAL"}:
            continue
        acronyms[tok] = acronyms.get(tok, 0) + 1
    acro = sorted(
        ({"term": k, "count": v} for k, v in acronyms.items() if v >= 5),
        key=lambda x: (-x["count"], x["term"]),
    )[:120]
    concepts = []
    for c in CONCEPTS:
        n = low.count(c)
        if n >= 2:
            concepts.append({"term": c, "count": n})
    # dedupe substrings (chain of thought vs chain-of-thought kept)
    concepts.sort(key=lambda x: (-x["count"], x["term"]))
    return {"acronyms": acro, "concepts": concepts}


def main():
    files = sorted(glob.glob(SRT_GLOB))
    assert len(files) == 9, f"expected 9 files, got {len(files)}"
    index = json.load(open("index.json", encoding="utf-8"))
    parts = []
    for entry, path in zip(index, files):
        segs = parse_srt(path)
        paras = merge_paragraphs(segs)
        duration = max(s[1] for s in segs) if segs else 0
        parts.append(
            {
                "n": int(entry["part"]),
                "id": entry["id"],
                "title": entry["title"],
                "file": os.path.basename(path),
                "duration": round(duration),
                "paras": paras,
                "outline": build_outline(paras),
            }
        )
        print(f"part {entry['part']}: {len(segs)} segs -> {len(paras)} paras, "
              f"{len(parts[-1]['outline'])} outline pts, {round(duration/60)} min")
    data = {
        "course": "Stanford CS329A — Self-Improving AI Agents",
        "source": "https://www.youtube.com/playlist?list=PLangBM27OtEA",
        "parts": parts,
        "glossary": build_glossary(parts),
    }
    with open("transcripts.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    tpl = open("template.html", encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    out = tpl.replace("/*__DATA__*/null", payload)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {OUT_HTML} ({len(out)/1024/1024:.1f} MB), transcripts.json")


if __name__ == "__main__":
    main()
