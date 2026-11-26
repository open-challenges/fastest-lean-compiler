#!/usr/bin/env python3
"""Judge an entry: build its toolchain and stock Lean's, time both on the workload, compare their theorems.

    # an entry as CI sees it: a commit of a public Lean 4 fork, everything built in a sandbox
    python3 scripts/verify.py --code https://github.com/OWNER/lean4/tree/<40-hex commit> --sandbox docker

    # stock Lean against itself: the baseline, and the runner's noise
    python3 scripts/verify.py --code stock --sandbox docker

    # your own toolchains, already built (no Docker): fast iteration on your own machine
    python3 scripts/verify.py --entry-toolchain ~/lean4/build/release/stage1 \\
        --stock-toolchain ~/lean4-stock/build/release/stage1

Steps:

1. Fetch the entry's commit and stock Lean's (bench/workload.json pins it), and list what the entry
   changes (the diff is shown on the pull request, and some kinds of change wait for a maintainer).
2. Build both toolchains from source the same way: `cmake --preset release` with clang, then make.
   With --sandbox docker this runs in a container with no network, no capabilities and a read-only
   root, where the build can write only its own source tree.
3. Build the exporter (harness/) with each toolchain.
4. Rounds. Each round salts a fresh copy of the workload (scripts/salt.py: one new theorem in every
   file), then builds it with each toolchain from clean, alternating which goes first. Only `lake
   build` is timed, by this script, outside the container. Then each toolchain exports the theorems
   it built (harness/ExportTheorems.lean), and the two exports must be identical, byte for byte.
5. The score is the speedup: the median over rounds of stock's build time divided by the entry's.

The verdict goes to <work>/verdict.json. Exit code 0 means the entry built the same theorems.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import entries  # noqa: E402
import salt  # noqa: E402

IMAGE = "flc-sandbox"
TOOLCHAIN_TIMEOUT = int(os.environ.get("FLC_TOOLCHAIN_TIMEOUT", 150 * 60))
BUILD_TIMEOUT = int(os.environ.get("FLC_BUILD_TIMEOUT", 60 * 60))
EXPORT_TIMEOUT = 30 * 60


def log(msg: str) -> None:
    print(f"[verify] {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


def load_workload() -> dict:
    with open(os.path.join(ROOT, "bench", "workload.json")) as fh:
        return json.load(fh)


def fetch(repo_url: str, sha: str, dest: str) -> None:
    """Check out one commit, and nothing else, into dest. The remote is recorded as origin because
    Lake compares a package's origin with its manifest, and would otherwise try to clone it again."""
    os.makedirs(dest, exist_ok=True)
    git = ["git", "-C", dest, "-c", "advice.detachedHead=false"]
    if not os.path.isdir(os.path.join(dest, ".git")):
        run(git + ["init", "-q"])
        run(git + ["remote", "add", "origin", repo_url])
    run(git + ["fetch", "-q", "--depth", "1", repo_url, sha], timeout=1800)
    run(git + ["checkout", "-q", "FETCH_HEAD"])
    got = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if got != sha:
        raise SystemExit(f"fetched {got}, expected {sha}")


# ---------------------------------------------------------------------------------------------- diff

def diff_summary(src: str, base: str) -> dict:
    """What the entry changes relative to stock Lean, and the flags that make it wait for a maintainer."""
    git = ["git", "-C", src]
    numstat = subprocess.run(git + ["diff", "--numstat", base, "HEAD"], capture_output=True, text=True, check=True).stdout
    files, added, deleted, binary = [], 0, 0, []
    for line in numstat.splitlines():
        a, d, path = line.split("\t", 2)
        if a == "-":
            binary.append(path)
            files.append({"path": path, "binary": True})
            continue
        added, deleted = added + int(a), deleted + int(d)
        files.append({"path": path, "added": int(a), "deleted": int(d)})
    patch = subprocess.run(git + ["diff", "--unified=0", base, "HEAD"], capture_output=True, text=True, errors="replace").stdout
    mentions = sorted({w.lower() for w in re.findall(r"(?i)cedar|flcsalt|flc_salt|batteries", "\n".join(
        l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")))})
    return {"files": len(files), "added": added, "deleted": deleted, "binary": binary,
            "largest": sorted(files, key=lambda f: -(f.get("added", 0) + f.get("deleted", 0)))[:15],
            "flags": flags(files, added + deleted, binary, mentions)}


def flags(files: list[dict], changed: int, binary: list[str], mentions: list[str]) -> list[str]:
    out = []
    if binary:
        out.append(f"changes {len(binary)} binary file(s): {', '.join(binary[:5])}")
    if any(f.get("added", 0) > 5000 for f in files):
        out.append("adds more than 5,000 lines to one file")
    if changed > 20000:
        out.append(f"changes {changed:,} lines in all")
    if any(f["path"].startswith("stage0/") for f in files):
        out.append("updates stage0, the bootstrap compiler")
    if mentions:
        out.append(f"the added lines mention the workload ({', '.join(mentions)})")
    return out


# ------------------------------------------------------------------------------------------- sandbox

def sandbox(cmd: str, *, cwd: str, rw: list[str], ro: list[str], toolchain: str | None, timeout: int, mode: str) -> float:
    """Run `bash -c cmd` in cwd, in the container or directly; return the wall time, measured here."""
    path = (f"{toolchain}/bin:" if toolchain else "") + "/usr/bin:/bin"
    if mode == "none":
        env = dict(os.environ, PATH=(f"{toolchain}/bin:" if toolchain else "") + os.environ["PATH"])
        start = time.monotonic()
        run(["bash", "-c", cmd], cwd=cwd, env=env, timeout=timeout)
        return time.monotonic() - start
    name = f"flc-{os.getpid()}-{secrets.token_hex(3)}"
    docker = ["docker", "run", "--rm", "--name", name, "--network", "none", "--cap-drop", "ALL",
              "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:exec",
              "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp", "-e", f"PATH={path}"]
    for p in rw:
        docker += ["-v", f"{p}:{p}"]
    for p in ro:
        docker += ["-v", f"{p}:{p}:ro"]
    docker += ["-w", cwd, IMAGE, "bash", "-c", cmd]
    start = time.monotonic()
    try:
        run(docker, timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        raise
    return time.monotonic() - start


def ensure_image(mode: str) -> None:
    if mode == "docker" and subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode:
        with open(os.path.join(ROOT, "harness", "sandbox.Dockerfile"), "rb") as fh:   # no build context
            run(["docker", "build", "-q", "-t", IMAGE, "-"], input=fh.read())


def tail(path: str, lines: int = 60) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            kept = [l.rstrip("\n") for l in fh if not l.startswith("✔")]
    except OSError:
        return ""
    return "\n".join(kept[-lines:])[-6000:]


def build_toolchain(src: str, mode: str) -> tuple[str, float]:
    """bench/workload.json's build command (cmake, then make) in src; returns (stage1 folder, minutes)."""
    stage1 = os.path.join(src, "build", "release", "stage1")
    secs = sandbox(f"({load_workload()['lean']['build']}) > make.log 2>&1",
                   cwd=src, rw=[src], ro=[], toolchain=None, timeout=TOOLCHAIN_TIMEOUT, mode=mode)
    if not os.path.isfile(os.path.join(stage1, "bin", "lean")):
        raise RuntimeError("the build finished without stage1/bin/lean")
    return stage1, secs / 60


def build_exporter(work: str, label: str, toolchain: str, mode: str, export_src: str) -> str:
    """The harness, built by this toolchain; returns the exporter binary."""
    d = os.path.join(work, f"exporter-{label}")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, ".lake", "packages"))
    for f in ("lakefile.toml", "lake-manifest.json", "ExportTheorems.lean"):
        shutil.copy(os.path.join(ROOT, "harness", f), d)
    shutil.copytree(export_src, os.path.join(d, ".lake", "packages", "lean4export"), symlinks=True)
    sandbox("lake build export-theorems > build.log 2>&1", cwd=d, rw=[d], ro=[toolchain], toolchain=toolchain,
            timeout=30 * 60, mode=mode)
    return os.path.join(d, ".lake", "build", "bin", "export-theorems")


# ---------------------------------------------------------------------------------------- the rounds

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def first_difference(a: str, b: str) -> dict:
    with open(a, "rb") as fa, open(b, "rb") as fb:
        for n, (la, lb) in enumerate(zip(fa, fb), 1):
            if la != lb:
                return {"line": n, "stock": la[:400].decode(errors="replace"), "entry": lb[:400].decode(errors="replace")}
    return {"line": None, "note": "one export is a prefix of the other"}


def one_build(work: str, project: dict, pristine: str, label: str, seed: int, toolchain: str, exporter: str, mode: str) -> dict:
    run_dir = os.path.join(work, f"run-{label}")
    shutil.rmtree(run_dir, ignore_errors=True)
    shutil.copytree(pristine, run_dir, symlinks=True)
    salted = salt.salt_tree(run_dir, seed)
    targets = " ".join(project["targets"])
    try:
        secs = sandbox(f"lake build {targets} > build.log 2>&1", cwd=run_dir, rw=[run_dir], ro=[toolchain],
                       toolchain=toolchain, timeout=BUILD_TIMEOUT, mode=mode)
    except subprocess.CalledProcessError:
        raise BuildFailed(label, "build", tail(os.path.join(run_dir, "build.log")))
    except subprocess.TimeoutExpired:
        raise BuildFailed(label, "build", f"lake build took longer than {BUILD_TIMEOUT // 60} minutes")
    out = os.path.join(work, f"theorems-{label}.ndjson")
    roots, prefixes = " ".join(project["export_roots"]), " ".join(project["prefixes"])
    try:
        sandbox(f"lake env {exporter} {roots} -- {prefixes} > theorems.ndjson 2> export.log", cwd=run_dir,
                rw=[run_dir], ro=[toolchain, os.path.dirname(exporter)], toolchain=toolchain,
                timeout=EXPORT_TIMEOUT, mode=mode)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise BuildFailed(label, "export", tail(os.path.join(run_dir, "export.log")))
    shutil.move(os.path.join(run_dir, "theorems.ndjson"), out)
    m = re.search(r"\[export\] (\d+) theorems", open(os.path.join(run_dir, "export.log"), errors="replace").read())
    return {"seconds": round(secs, 1), "salted_files": salted, "export": out, "export_bytes": os.path.getsize(out),
            "sha256": sha256(out), "theorems": int(m.group(1)) if m else None}


class BuildFailed(Exception):
    def __init__(self, label: str, stage: str, detail: str):
        super().__init__(f"{label} {stage} failed")
        self.label, self.stage, self.detail = label, stage, detail


def rounds(work: str, project: dict, pristine: str, toolchains: dict[str, str], exporters: dict[str, str],
           n: int, mode: str) -> list[dict]:
    out = []
    for r in range(n):
        seed = secrets.randbits(64)
        order = ["stock", "entry"] if r % 2 == 0 else ["entry", "stock"]
        res = {}
        for label in order:
            log(f"round {r + 1}/{n}: {label}")
            res[label] = one_build(work, project, pristine, label, seed, toolchains[label], exporters[label], mode)
            log(f"round {r + 1}: {label} built in {res[label]['seconds']} s, {res[label]['theorems']} theorems, "
                f"export {res[label]['export_bytes']:,} bytes {res[label]['sha256'][:16]}")
        same = res["stock"]["sha256"] == res["entry"]["sha256"]
        row = {"round": r + 1, "seed": f"{seed:016x}", "first": order[0], "same_theorems": same,
               "stock": {k: v for k, v in res["stock"].items() if k != "export"},
               "entry": {k: v for k, v in res["entry"].items() if k != "export"},
               "speedup": round(res["stock"]["seconds"] / res["entry"]["seconds"], 4)}
        if not same:
            row["difference"] = first_difference(res["stock"]["export"], res["entry"]["export"])
        for label in res:
            os.remove(res[label]["export"])
        out.append(row)
        if not same:
            break
    return out


# ---------------------------------------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--code", help="https://github.com/OWNER/REPO/tree/<40-hex commit>, or 'stock'")
    who.add_argument("--entry-toolchain", help="an entry toolchain you built already (its stage1 folder)")
    ap.add_argument("--stock-toolchain", help="stock Lean's stage1 folder, built the same way; built here if absent")
    ap.add_argument("--stock-dir", help="where to keep stock Lean's source and build between runs")
    ap.add_argument("--sandbox", choices=["docker", "none"], default="none")
    ap.add_argument("--rounds", type=int, default=int(os.environ.get("FLC_ROUNDS", 3)))
    ap.add_argument("--work", help="work folder (default: a new temporary one)")
    args = ap.parse_args(argv)

    wl = load_workload()
    base = wl["lean"]["commit"]
    project = wl["projects"][0]
    work = os.path.abspath(args.work or tempfile.mkdtemp(prefix="flc-"))
    os.makedirs(work, exist_ok=True)
    verdict: dict = {"code": args.code, "base": f"{wl['lean']['tag']} ({base[:7]})", "workload": project["title"],
                     "machine": {"cpus": os.cpu_count()},
                     "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def finish(ok: bool, **kw) -> int:
        verdict.update(kw, ok=ok, finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with open(os.path.join(work, "verdict.json"), "w") as fh:
            json.dump(verdict, fh, indent=2)
        print(json.dumps(verdict, indent=2))
        return 0 if ok else 1

    ensure_image(args.sandbox)
    toolchains: dict[str, str] = {}
    minutes: dict[str, float] = {}

    # stock Lean, built here unless given or kept from an earlier run
    if args.stock_toolchain:
        toolchains["stock"] = os.path.abspath(args.stock_toolchain)
    else:
        sdir = os.path.abspath(args.stock_dir or os.path.join(work, "stock"))
        stage1 = os.path.join(sdir, "build", "release", "stage1")
        if os.path.isfile(os.path.join(stage1, "bin", "lean")):
            log(f"stock Lean: reusing {stage1}")
        else:
            try:
                fetch(f"https://github.com/{wl['lean']['repo']}", base, sdir)
                stage1, minutes["stock"] = build_toolchain(sdir, args.sandbox)
            except Exception as e:   # noqa: BLE001  the judge's own failure, not the entry's
                return finish(False, stage="stock", error=f"could not build stock Lean: {e}",
                              log_tail=tail(os.path.join(sdir, "make.log")))
        toolchains["stock"] = stage1

    # the entry
    if args.entry_toolchain:
        toolchains["entry"] = os.path.abspath(args.entry_toolchain)
    elif args.code == "stock":
        toolchains["entry"] = toolchains["stock"]
        verdict["commit"] = base
    else:
        m = entries.CODE_URL.match(args.code.strip())
        if not m:
            return finish(False, stage="fetch", error="code must be https://github.com/OWNER/REPO/tree/<40-hex commit>")
        owner, repo, sha = m.groups()
        verdict["commit"] = sha
        src = os.path.join(work, "entry")
        try:
            fetch(f"https://github.com/{owner}/{repo}", sha, src)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, SystemExit) as e:
            why = e.code if isinstance(e, SystemExit) else "git could not fetch that commit (is the repository public, and the hash complete?)"
            return finish(False, stage="fetch", error=str(why))
        try:
            run(["git", "-C", src, "fetch", "-q", "--depth", "1", f"https://github.com/{wl['lean']['repo']}", base], timeout=1800)
            verdict["diff"] = diff_summary(src, base)
        except subprocess.CalledProcessError:
            verdict["diff"] = {"error": "could not diff against stock Lean"}
        if not os.path.isfile(os.path.join(src, "CMakePresets.json")):
            return finish(False, stage="fetch", error="the commit has no CMakePresets.json at its root: is it a Lean 4 source tree?")
        try:
            toolchains["entry"], minutes["entry"] = build_toolchain(src, args.sandbox)
        except subprocess.TimeoutExpired:
            return finish(False, stage="toolchain", error=f"building the toolchain took longer than {TOOLCHAIN_TIMEOUT // 60} minutes")
        except (subprocess.CalledProcessError, RuntimeError) as e:
            return finish(False, stage="toolchain", error=f"building the toolchain failed: {e}",
                          log_tail=tail(os.path.join(src, "make.log")))
    verdict["toolchain_build_minutes"] = {k: round(v, 1) for k, v in minutes.items()}

    # the workload and the exporter's sources, fetched here (the sandbox has no network)
    wsrc = os.path.join(work, "workload", project["name"])
    pristine = os.path.join(wsrc, project["dir"]) if project.get("dir") else wsrc
    if not os.path.isdir(pristine):
        fetch(f"https://github.com/{project['repo']}", project["commit"], wsrc)
        for pkg in project.get("packages", []):
            fetch(f"https://github.com/{pkg['repo']}", pkg["commit"], os.path.join(pristine, ".lake", "packages", pkg["name"]))
    export_src = os.path.join(work, "lean4export")
    if not os.path.isdir(export_src):
        with open(os.path.join(ROOT, "harness", "lake-manifest.json")) as fh:
            rev = next(p["rev"] for p in json.load(fh)["packages"] if p["name"] == "lean4export")
        fetch("https://github.com/leanprover/lean4export", rev, export_src)

    exporters: dict[str, str] = {}
    for label in ("stock", "entry"):
        if label == "entry" and toolchains["entry"] == toolchains["stock"]:
            exporters["entry"] = exporters["stock"]
            continue
        try:
            exporters[label] = build_exporter(work, label, toolchains[label], args.sandbox, export_src)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            stage = "stock" if label == "stock" else "exporter"
            return finish(False, stage=stage, error=f"the {label} toolchain could not build the exporter (harness/)",
                          log_tail=tail(os.path.join(work, f"exporter-{label}", "build.log")))

    try:
        rows = rounds(work, project, pristine, toolchains, exporters, args.rounds, args.sandbox)
    except BuildFailed as e:
        stage = "stock" if e.label == "stock" else e.stage
        return finish(False, stage=stage, error=f"the {e.label} toolchain's {e.stage} of the workload failed", log_tail=e.detail)
    verdict["rounds"] = rows
    if not all(r["same_theorems"] for r in rows):
        return finish(False, stage="compare", error="the entry's theorems differ from stock Lean's", difference=rows[-1].get("difference"))
    speedup = statistics.median(r["speedup"] for r in rows)
    return finish(True, stage="done", speedup=round(speedup, 3),
                  stock_seconds=round(statistics.median(r["stock"]["seconds"] for r in rows), 1),
                  entry_seconds=round(statistics.median(r["entry"]["seconds"] for r in rows), 1),
                  theorems=rows[0]["entry"]["theorems"], export_bytes=rows[0]["entry"]["export_bytes"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
