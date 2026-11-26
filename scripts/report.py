#!/usr/bin/env python3
"""Turn a verdict into the pull request comment and the merge decision.

    python3 scripts/report.py --verdict verdict.json [--entry entry.json] --out out/ [--run-url URL]

Writes out/comment.md and out/decision.json ({"merge": bool, "record": bool, "labels": [...]}) and
prints a summary for the job page. A verified entry that sets a record (a speedup at least
entries.RECORD_MARGIN above the best so far) is merged at once, unless its diff raised a flag;
every other verified entry waits for a maintainer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import entries  # noqa: E402

ROOT = os.path.dirname(HERE)
REPO_URL = "https://github.com/" + os.environ.get("GITHUB_REPOSITORY", "open-challenges/fastest-lean-compiler")


def fmt_secs(s: float) -> str:
    return f"{int(s // 60)} min {s % 60:04.1f} s" if s >= 60 else f"{s:.1f} s"


def rounds_table(rows: list[dict]) -> list[str]:
    out = ["| Round | First | Stock Lean | Entry | Speedup | Same theorems |", "|---:|---|---:|---:|---:|---|"]
    for r in rows:
        out.append(f"| {r['round']} | {r['first']} | {fmt_secs(r['stock']['seconds'])} | {fmt_secs(r['entry']['seconds'])} "
                   f"| {r['speedup']:.3f}× | {'yes' if r['same_theorems'] else '**no**'} |")
    return out


def decide(verdict: dict, entry: dict | None, standing: list[entries.Entry]) -> tuple[dict, list[str]]:
    lines: list[str] = []
    labels: list[str] = []
    flags = (verdict.get("diff") or {}).get("flags") or []
    if entry is not None and not entry.get("ok"):
        return {"merge": False, "record": False, "labels": ["invalid"]}, [
            "### Not an entry yet", "", f"{entry.get('error')}", "",
            f"See [How to enter]({REPO_URL}#how-to-enter)."]
    if not verdict.get("ok"):
        stage = verdict.get("stage")
        if stage == "stock":
            labels.append("judge-problem")
            lines += ["### Inconclusive: the judge's own build of stock Lean failed", "",
                      "This is not your entry's fault. A maintainer will look; the run can be retried."]
        else:
            labels.append("failed")
            lines += [f"### Not verified ({stage})", "", f"{verdict.get('error')}"]
        if verdict.get("difference"):
            d = verdict["difference"]
            lines += ["", f"First difference in the theorem export, line {d.get('line')}:", "",
                      "```", f"stock: {d.get('stock', '')[:300]}", f"entry: {d.get('entry', '')[:300]}", "```"]
        if verdict.get("log_tail"):
            lines += ["", "<details><summary>Log</summary>", "", "```", verdict["log_tail"][-4000:], "```", "", "</details>"]
        return {"merge": False, "record": False, "labels": labels}, lines

    speedup = verdict["speedup"]
    record = entry is not None and entries.is_record(speedup, standing)
    best = entries.best(standing)
    labels.append("verified")
    head = f"### Verified: {speedup:.3f}× stock Lean"
    lines += [head, "",
              f"Same {verdict.get('theorems'):,} theorems as stock Lean {verdict.get('base')}, byte for byte, in every round. "
              f"Median `lake build` of the workload: stock {fmt_secs(verdict['stock_seconds'])}, "
              f"entry {fmt_secs(verdict['entry_seconds'])}.", "", *rounds_table(verdict["rounds"]), ""]
    if record:
        labels.append("record")
        lines.append(f"**A new record**: the best verified speedup so far is {best:.3f}×, and a record needs "
                     f"{best * entries.RECORD_MARGIN:.3f}× or more.")
    elif entry is not None:
        lines.append(f"Not a record: the best verified speedup is {best:.3f}×, and a record needs "
                     f"{best * entries.RECORD_MARGIN:.3f}× or more (a margin above the runner's noise).")
    diff = verdict.get("diff") or {}
    if diff.get("files") is not None:
        lines += ["", f"The entry changes {diff['files']} file(s) of Lean, +{diff['added']:,} −{diff['deleted']:,} lines."]
        if diff.get("largest"):
            lines += ["", "<details><summary>Largest changes</summary>", ""]
            lines += [f"- `{f['path']}`" + (" (binary)" if f.get("binary") else f" +{f['added']} −{f['deleted']}") for f in diff["largest"]]
            lines += ["", "</details>"]
    if flags:
        labels.append("needs-review")
        lines += ["", "A maintainer reads the diff before this is merged, because it " + "; ".join(flags) + "."]
    merge = record and not flags
    if record and merge:
        lines += ["", "Merging."]
    elif record:
        lines += ["", "Waiting for a maintainer."]
    return {"merge": merge, "record": record, "labels": labels}, lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--entry")
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-url", default="")
    args = ap.parse_args()
    try:
        with open(args.verdict) as fh:
            verdict = json.load(fh)
    except (OSError, ValueError):
        verdict = {"ok": False, "stage": "judge", "error": "the run wrote no verdict (see the log)"}
    entry = None
    if args.entry and os.path.exists(args.entry):
        with open(args.entry) as fh:
            entry = json.load(fh)
    decision, lines = decide(verdict, entry, entries.load(ROOT))
    if args.run_url:
        lines += ["", f"[Run log]({args.run_url}) · judged on {verdict.get('machine', {}).get('cpus', '?')} cores"]
    os.makedirs(args.out, exist_ok=True)
    text = "\n".join(lines) + "\n"
    with open(os.path.join(args.out, "comment.md"), "w") as fh:
        fh.write(text)
    with open(os.path.join(args.out, "decision.json"), "w") as fh:
        json.dump(decision, fh)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
