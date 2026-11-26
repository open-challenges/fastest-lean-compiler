#!/usr/bin/env python3
"""The exporter on a toy project, with the Lean on PATH: what the judge relies on, end to end.

    python3 harness/tests/run_toy.py <export-theorems binary>

1. Two clean builds of harness/tests/toy export the same bytes (the judge compares bytes).
2. The export holds the toy's theorems, the private one of the module-system file included, and
   what they depend on, and no metadata line (it would name the toolchain's git hash).
3. Salted (scripts/salt.py) the same way, two builds still agree, with one more theorem per file;
   salted differently, they don't.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import salt  # noqa: E402


def build_and_export(exporter: str, seed: int | None) -> tuple[str, bytes, str]:
    d = tempfile.mkdtemp(prefix="toy-")
    shutil.copytree(os.path.join(HERE, "toy"), d, dirs_exist_ok=True)
    if seed is not None:
        assert salt.salt_tree(d, seed) == 3, "toy has three source files to salt"
    subprocess.run(["lake", "build"], cwd=d, check=True, capture_output=True)
    p = subprocess.run(["lake", "env", exporter, "Toy", "--", "Toy"], cwd=d, check=True, capture_output=True)
    return hashlib.sha256(p.stdout).hexdigest(), p.stdout, p.stderr.decode()


def names(ndjson: bytes) -> set[str]:
    """The constants an export declares, by name (enough for these checks)."""
    lines = [json.loads(l) for l in ndjson.splitlines()]
    strs: dict[int, str] = {0: ""}
    for o in lines:
        if "in" in o and "str" in o:
            pre = strs.get(o["str"]["pre"], "")
            strs[o["in"]] = (pre + "." if pre else "") + o["str"]["str"]
        elif "in" in o and "num" in o:
            pre = strs.get(o["num"]["pre"], "")
            strs[o["in"]] = (pre + "." if pre else "") + str(o["num"]["i"])
    out = set()
    for o in lines:
        for kind in ("thm", "def", "axiom", "opaque", "quot"):
            if kind in o:
                out.add(strs[o[kind]["name"]])
        if "inductive" in o:
            for t in o["inductive"].get("types", []):
                out.add(strs[t["name"]])
    return out


def main() -> int:
    exporter = os.path.abspath(sys.argv[1])
    a, out_a, err = build_and_export(exporter, None)
    b, _, _ = build_and_export(exporter, None)
    print(err.strip())
    assert a == b, "two clean builds exported different bytes"
    assert b'"meta"' not in out_a.splitlines()[0], "the export starts with a metadata line"
    got = names(out_a)
    for n in ("Toy.A.double_eq", "Toy.A.double_double", "Toy.B.add_comm'", "Toy.B.length_append_nil", "Toy.A.double", "Nat.add_comm"):
        assert n in got, f"{n} is missing from the export"
    assert any(n.endswith("helper") for n in got), "the private theorem of the module-system file is missing"
    count = int(re.search(r"\[export\] (\d+) theorems", err).group(1))
    assert count >= 5, err
    s1, out_s, err_s = build_and_export(exporter, 7)
    s2, _, _ = build_and_export(exporter, 7)
    s3, _, _ = build_and_export(exporter, 8)
    assert s1 == s2, "two builds salted the same way exported different bytes"
    assert s1 != s3 and s1 != a, "salting did not change the export"
    assert f"[export] {count + 3} theorems" in err_s, err_s
    print(f"ok: clean {a[:16]}, salted {s1[:16]}, {len(got)} constants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
