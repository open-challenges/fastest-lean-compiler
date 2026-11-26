#!/usr/bin/env python3
"""Write the leaderboard into README.md (between the leaderboard markers) from submissions/*/.

Each verified entry has SUBMISSION.md, written by its author, and verdict.json, written by CI when
the entry was merged: the speedup on the board is CI's measurement, never the author's.

    python3 scripts/leaderboard.py          # rewrite README.md
    python3 scripts/leaderboard.py --check  # exit 1 if README.md is out of date
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entries  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "<!-- leaderboard:start -->", "<!-- leaderboard:end -->"


def render(root: str) -> str:
    out = ["| # | Speedup | Build (stock → entry) | Entry | By | Agent | Date |",
           "|---:|---:|---:|---|---|---|---|"]
    rank = 0
    for e in entries.standings(entries.load(root)):
        v = e.verdict or {}
        if not e.baseline:
            rank += 1
        who = ", ".join(f"[@{a}](https://github.com/{a})" for a in e.authors)
        agent = " via ".join(x for x in (e.agent.get("model"), e.agent.get("harness")) if x) or "—"
        title = f"[{e.title}](submissions/{e.folder}/SUBMISSION.md)" + (" (baseline)" if e.baseline else "")
        times = f"{v.get('stock_seconds', 0) / 60:.1f} → {v.get('entry_seconds', 0) / 60:.1f} min"
        out.append(f"| {'—' if e.baseline else rank} | **{e.speedup:.3f}×** | {times} | {title} · [code]({e.code}) "
                   f"| {who} | {agent} | {e.date or '—'} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    path = os.path.join(ROOT, "README.md")
    with open(path, encoding="utf-8") as fh:
        readme = fh.read()
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: f"{START}\n{render(ROOT)}{END}", readme, flags=re.S)
    if args.check:
        if new != readme:
            print("README.md's leaderboard is out of date: run python3 scripts/leaderboard.py", file=sys.stderr)
            return 1
        return 0
    if new != readme:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
        print("README.md updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
