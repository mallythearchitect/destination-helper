"""Turn the Destination Helper brief (a .docx) into the pack's JSON source.

    .venv/bin/python scripts/extract_helper_doc.py ~/Desktop/destination-helper-v3.docx

Writes packs/source/destination-helper-<version>-<date>.json. The document's
structure is the contract: question codes (GO-01), workflows (W01 · Title,
Runs when / Steps / Gives / Track record), guardrails (G01 · rule. Why (...)),
the methods sections, and one region pack per country. Then run
packs/build_helper.py to build packs/helper.sqlite.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "packs" / "source"

Q_RE = re.compile(r"^- ([A-Z]+-\d\d) (.*?)(?: NEW)?$")
W_RE = re.compile(r"^W(\d\d) · (.*?)(?: NEW)?$")
G_RE = re.compile(r"^- (G\d\d) · (.*)$")
SEC_RE = re.compile(r"^([A-Z]+) — (.+)$")
NUM_RE = re.compile(r"^\d+\.\s+(.*)$")


def plain(docx: pathlib.Path) -> list[str]:
    txt = subprocess.run(["pandoc", "-t", "plain", "--wrap=none", str(docx)], check=True, capture_output=True, text=True).stdout
    return [ln.rstrip() for ln in txt.splitlines()]


def find(lines: list[str], startswith: str, after: int = 0) -> int:
    for i in range(after, len(lines)):
        if lines[i].startswith(startswith):
            return i
    raise SystemExit(f"heading not found: {startswith!r}")


def bullets(lines: list[str]) -> list[str]:
    """Top-level bullets; an indented sub-bullet is folded into its parent."""
    out: list[str] = []
    for ln in lines:
        if ln.startswith("- "):
            out.append(ln[2:].strip())
        elif ln.startswith("  - ") and out:
            out[-1] += "\n  • " + ln.strip()[2:]
    return out


def is_heading(ln: str) -> bool:
    return bool(ln) and not ln.startswith(("- ", "  ")) and not NUM_RE.match(ln) and len(ln) <= 90 and not ln.endswith((".", ":"))


def by_heading(lines: list[str]) -> list[dict]:
    """[{heading, lines}] for prose parts (the brief, the market scan, a region pack)."""
    out, cur = [], None
    for ln in lines:
        if not ln:
            continue
        if is_heading(ln):
            cur = {"heading": ln, "lines": []}
            out.append(cur)
        elif cur is not None:
            cur["lines"].append(ln[2:].strip() if ln.startswith("- ") else ("  • " + ln.strip()[2:] if ln.startswith("  - ") else ln))
    return out


def questions(lines: list[str]) -> tuple[list[dict], list[dict]]:
    sections, qs, sec = [], [], None
    for ln in lines:
        m = SEC_RE.match(ln)
        if m and " " not in m.group(1):
            sec = m.group(1)
            sections.append({"code": sec, "label": m.group(2)})
            continue
        m = Q_RE.match(ln)
        if m and sec:
            qs.append({"code": m.group(1), "section": sec, "text": m.group(2), "new": ln.endswith(" NEW")})
    return sections, qs


def workflows(lines: list[str]) -> tuple[str, list[dict]]:
    run_order = next((ln for ln in lines if ln.startswith("Run order:")), "")
    out, w = [], None
    for ln in lines:
        m = W_RE.match(ln)
        if m:
            w = {"code": f"W{m.group(1)}", "title": m.group(2), "new": ln.endswith(" NEW"), "runs_when": "", "steps": [], "gives": "", "track_record": ""}
            out.append(w)
            continue
        if w is None or not ln:
            continue
        if ln.startswith("Runs when:"):
            w["runs_when"] = ln.partition(":")[2].strip()
        elif ln.startswith("Steps:"):
            rest = ln.partition(":")[2].strip()
            if rest:
                w["steps"] = [s.strip().rstrip(".") for s in rest.split("→")]
        elif ln.startswith("Gives:"):
            w["gives"] = ln.partition(":")[2].strip()
        elif ln.startswith("Track record:"):
            w["track_record"] = ln.partition(":")[2].strip()
        else:
            m = NUM_RE.match(ln)
            if m:
                w["steps"].append(m.group(1).strip())
    return run_order, out


def guardrails(lines: list[str]) -> list[dict]:
    out = []
    for ln in lines:
        m = G_RE.match(ln)
        if not m:
            continue
        rule, _, why = m.group(2).partition(" Why ")
        why = re.sub(r"^\((.*?)\):\s*", r"\1: ", why)
        out.append({"code": m.group(1), "rule": rule.strip(), "why": why.strip()})
    return out


def sources(lines: list[str]) -> list[dict]:
    out = []
    for b in bullets(lines):
        new = b.endswith(" NEW")
        b = b[:-4] if new else b
        name, sep, text = b.partition(":")
        if not sep or len(name) > 90:
            name, text = b, ""
        out.append({"name": name.strip(), "text": text.strip(), "new": new})
    return out


def check_groups(lines: list[str]) -> dict[str, list[dict]]:
    out, grp = {}, None
    for ln in lines:
        if not ln:
            continue
        if is_heading(ln):
            grp = ln
            out[grp] = []
        elif grp and ln.startswith("- "):
            t = ln[2:].strip()
            new = t.endswith(" NEW")
            out[grp].append({"text": t[:-4] if new else t, "new": new})
    return out


def region_pack(lines: list[str], name: str) -> dict:
    parts = by_heading(lines)
    intro = ""
    if parts and parts[0]["heading"] == f"{name} pack":
        intro = " ".join(parts[0]["lines"])
        parts = parts[1:]
    sections, examples = {}, []
    for p in parts:
        if p["heading"].startswith("Worked examples"):
            for ln in p["lines"]:
                m = re.match(r"^([A-Z]+-\d\d) (.*)$", ln)
                if m:
                    examples.append({"code": m.group(1), "text": m.group(2)})
        else:
            sections[p["heading"]] = p["lines"]
    return {"name": name, "intro": intro, "sections": sections, "worked_examples": examples}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    docx = pathlib.Path(argv[1]).expanduser()
    L = plain(docx)
    title = L[0]
    version = (re.search(r"\((v\d+)\)", title) or re.search(r"(v\d+)", docx.stem) or [None, "v?"])[1]
    i_a, i_b = find(L, "Part A"), find(L, "Part B")
    i_how, i_1, i_2, i_3, i_4, i_5 = (find(L, "How the capability list works"), find(L, "Part 1"), find(L, "Part 2"),
                                     find(L, "Part 3"), find(L, "Part 4"), find(L, "Part 5"))
    i_log = find(L, "Change log")
    p2 = L[i_2:i_3]
    j = {k: find(p2, s) for k, s in {"setup": "Set up every new trip", "defaults": "Defaults for every answer", "sources": "Where the answers come from",
                                      "checks": "Checks", "formats": "Answer formats"}.items()}
    sections, qs = questions(L[i_1:i_2])
    run_order, wfs = workflows(L[i_3:i_4])
    p5 = L[i_5:i_log]
    i_t = find(p5, "Template")
    packs_at = [(k, ln[:-5]) for k, ln in enumerate(p5) if ln.endswith(" pack") and not ln.startswith(("- ", "Template"))]
    region_template = bullets(p5[i_t:packs_at[0][0]] if packs_at else p5[i_t:])
    region_packs = []
    for n, (k, name) in enumerate(packs_at):
        end = packs_at[n + 1][0] if n + 1 < len(packs_at) else len(p5)
        region_packs.append(region_pack(p5[k:end], name))
    doc = {
        "meta": {"title": title, "version": version, "extracted": date.today().isoformat(), "source_docx": docx.name,
                 "updated_line": next((ln for ln in L[:12] if "Updated" in ln), "")},
        "brief": by_heading(L[i_a + 1:i_b]),
        "market": by_heading(L[i_b + 1:i_how]),
        "how_it_is_built": by_heading(L[i_how + 1:i_1]),
        "sections": sections, "questions": qs,
        "setup": bullets(p2[j["setup"]:j["defaults"]]), "defaults": bullets(p2[j["defaults"]:j["sources"]]),
        "sources": sources(p2[j["sources"]:j["checks"]]), "checks": check_groups(p2[j["checks"] + 1:j["formats"]]),
        "formats": bullets(p2[j["formats"]:]),
        "run_order": run_order, "workflows": wfs, "guardrails": guardrails(L[i_4:i_5]),
        "region_template": region_template, "region_packs": region_packs,
        "changelog": bullets(L[i_log:]),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"destination-helper-{version}-{date.today().isoformat()}.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"{out.relative_to(ROOT)}: {len(qs)} questions in {len(sections)} sections, {len(wfs)} workflows, {len(doc['guardrails'])} guardrails, "
          f"{len(doc['sources'])} sources, {sum(len(v) for v in doc['checks'].values())} checks, {len(region_packs)} region pack(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
