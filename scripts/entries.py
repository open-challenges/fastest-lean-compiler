"""SUBMISSION.md files and the verdicts CI stored next to them: parsing, validation, standings."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import yaml

SUBMISSIONS = "submissions"
FOLDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
# a commit of a public GitHub repository holding a Lean 4 source tree at its root
CODE_URL = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})/(?:tree|commit)/([0-9a-f]{40})/?$")
# a new record must beat the best verified speedup by this factor, which is above the runner's noise
RECORD_MARGIN = 1.03


class EntryError(Exception):
    pass


@dataclass
class Entry:
    folder: str
    title: str
    authors: list[str]
    date: str
    code: str
    baseline: bool = False
    agent: dict = field(default_factory=dict)
    verdict: dict | None = None

    @property
    def commit(self) -> str:
        m = CODE_URL.match(self.code)
        return m.group(3) if m else ""

    @property
    def short_code(self) -> str:
        m = CODE_URL.match(self.code)
        return f"{m.group(1)}/{m.group(2)}@{m.group(3)[:7]}" if m else self.code

    @property
    def speedup(self) -> float | None:
        v = self.verdict or {}
        # CI's verdict counts only for the commit it judged
        return v.get("speedup") if v.get("ok") and v.get("commit") == self.commit else None


def front_matter(text: str) -> dict:
    m = re.match(r"^﻿?---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        raise EntryError("SUBMISSION.md must start with YAML front matter between --- lines")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise EntryError(f"the front matter is not valid YAML: {str(e).splitlines()[0]}") from None
    if not isinstance(meta, dict):
        raise EntryError("the front matter must be a mapping")
    return meta


def parse(folder: str, text: str) -> Entry:
    meta = front_matter(text)
    if str(meta.get("spec", "")).strip() != "submission.md/v1":
        raise EntryError("spec: submission.md/v1 is required")
    authors = meta.get("authors") or ([meta["author"]] if meta.get("author") else [])
    if not isinstance(authors, list) or not authors or not all(isinstance(a, str) and HANDLE.match(a.lstrip("@")) for a in authors):
        raise EntryError("author (or authors) must be GitHub handles")
    code = str(meta.get("code", "")).strip()
    if not CODE_URL.match(code):
        raise EntryError("code must be https://github.com/OWNER/REPO/tree/<40-hex commit>, a commit of your Lean 4 fork")
    date = meta.get("date")
    agent = meta.get("agent") if isinstance(meta.get("agent"), dict) else {}
    return Entry(folder=folder, title=str(meta.get("title") or folder)[:140], authors=[a.lstrip("@") for a in authors],
                 date=str(date)[:10] if date else "", code=code, baseline=meta.get("baseline") is True,
                 agent={k: str(v)[:80] for k, v in agent.items() if k in ("model", "harness", "role")})


def load(root: str) -> list[Entry]:
    out = []
    base = os.path.join(root, SUBMISSIONS)
    for folder in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, folder, "SUBMISSION.md")
        if not (FOLDER.match(folder) and os.path.isfile(path)):
            continue
        with open(path, encoding="utf-8") as fh:
            e = parse(folder, fh.read())
        vpath = os.path.join(base, folder, "verdict.json")
        if os.path.isfile(vpath):
            with open(vpath, encoding="utf-8") as fh:
                e.verdict = json.load(fh)
        out.append(e)
    return out


def standings(entries: list[Entry]) -> list[Entry]:
    """Verified entries, fastest first; ties go to the earlier entry. The baseline is among them."""
    rows = [e for e in entries if e.speedup is not None]
    # the baseline is stock against itself: 1 by definition, whatever noise its self-check measured
    return sorted(rows, key=lambda e: (-(1.0 if e.baseline else e.speedup), e.date or "9999"))


def best(entries: list[Entry]) -> float:
    """The speedup to beat: the best verified entry's, or stock Lean's 1.00."""
    return max([1.0] + [e.speedup for e in entries if e.speedup is not None and not e.baseline])


def is_record(speedup: float, entries: list[Entry]) -> bool:
    return speedup >= best(entries) * RECORD_MARGIN
