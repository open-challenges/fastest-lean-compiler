"""Salt a workload before a timed build: append one fresh theorem to every Lean source file.

Each round of the judge picks a new random seed and salts both copies of the workload, stock's and
the entry's, the same way. Every file then differs from anything a toolchain could have stored, so
no build can be replayed from saved output, and both builds must still export the same theorems,
salt included. The salt itself costs nothing to elaborate: one closed `Nat` equation per file.
"""
from __future__ import annotations

import os
import random
import re

SALT = ("\n\n-- appended by the fastest-lean-compiler judge for one timed build\n"
        "theorem flcSalt_{tag} : _root_.Nat.add {a} {b} = {c} := _root_.rfl\n")
PRELUDE = re.compile(r"^\s*prelude\b", re.M)


def lean_files(root: str) -> list[str]:
    """The workload's Lean sources in a fixed order, packages included, build output and git excluded."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d != ".git" and not (d == "build" and os.path.basename(dirpath) == ".lake"))
        for f in sorted(filenames):
            if f.endswith(".lean") and f != "lakefile.lean":
                out.append(os.path.join(dirpath, f))
    return out


def salt_tree(root: str, seed: int) -> int:
    """Append a salt theorem to every source file under root; returns how many files were salted.
    Files in `prelude` mode are left alone: they have no `Nat` to state the salt with."""
    rng = random.Random(seed)
    n = 0
    for path in lean_files(root):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        a, b, tag = rng.randrange(10**6), rng.randrange(10**6), f"{rng.getrandbits(48):012x}"
        if PRELUDE.search(text[:4000]):
            continue
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(SALT.format(tag=tag, a=a, b=b, c=a + b))
        n += 1
    return n
