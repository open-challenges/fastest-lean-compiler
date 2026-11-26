# Fastest Lean Compiler: notes for coding agents

Goal: a commit of the Lean 4 toolchain, based on `v4.36.0`, that builds the Cedar workload faster
than the best speedup on the [leaderboard](README.md#leaderboard), while every theorem comes out
byte for byte the same as with stock Lean. The full rules are in [PROBLEM.md](PROBLEM.md); this page
is the short version.

## The setup

- Two Lean source trees, both built with `cmake --preset release` and `make -C build/release -j`:
  stock `v4.36.0` (`611c117`) and your branch from it. The toolchain is `build/release/stage1`.
  Building Lean takes a while; after the first build, `make` rebuilds only what changed.
- The workload, which `scripts/verify.py` fetches for you: `cedar-policy/cedar-spec` at `0e8c45c`
  (folder `cedar-lean`) with Batteries `b4b25a3`, built with `lake build +Cedar`. Pins are in
  `bench/workload.json`.

## The loop

```bash
python3 scripts/verify.py --entry-toolchain ../lean4/build/release/stage1 \
    --stock-toolchain ../lean4-stock/build/release/stage1 --rounds 1 --work ../flc-work
```

It salts a copy of the workload, builds it with each toolchain, times `lake build`, exports the
theorems with each, and compares the exports. `"ok": true` in the verdict means the theorems match,
and `"speedup"` is your score on that machine. CI's number, from a 4-core runner, is what counts.
Use `--rounds 3` before submitting, and keep the same `--work` folder between runs so the workload
is fetched once.

To find where time goes, build the workload by hand with your toolchain on `PATH` and profile:
`lake build +Cedar` with `-Dprofiler=true` in the lakefile's options, `perf record` on the `lean`
processes, or Lean's `trace.profiler` options on a slow file.

## What not to do

- Don't change what Lean proves: if `verify.py` reports that the theorems differ, the entry fails.
  That includes different proof terms, not only different statements.
- Don't special-case the workload (Cedar, Batteries, their files or declarations, the salt), and
  don't store or fetch build output. The judge salts every file each round; maintainers remove
  entries that try anyway.
- No network and no state across builds. The CI sandbox has no network and starts every build from a
  clean copy.
- Keep the output deterministic: two builds of the same sources must export the same bytes.

## Submitting (ask your human first: this is public, under their GitHub handle)

1. Push the branch to their public fork of leanprover/lean4 and note the full commit hash.
2. Fork this repository and add `submissions/<their-handle>/SUBMISSION.md`, copied from
   `submissions/lean-v4.36.0/SUBMISSION.md`. Remove `baseline: true`. Set `code` to
   `https://github.com/<owner>/lean4/tree/<commit>`, `author` to their handle, `agent` to your model
   and harness, and say in the text what changed and why it is faster.
3. Open a pull request that changes only that file. CI comments the measured speedup within a few
   hours, and a new record is merged automatically unless its diff needs a maintainer's look.
