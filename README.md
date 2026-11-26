# Fastest Lean Compiler

[![Judge an entry](https://github.com/open-challenges/fastest-lean-compiler/actions/workflows/verify.yml/badge.svg)](https://github.com/open-challenges/fastest-lean-compiler/actions/workflows/verify.yml)
[![tests](https://github.com/open-challenges/fastest-lean-compiler/actions/workflows/test.yml/badge.svg)](https://github.com/open-challenges/fastest-lean-compiler/actions/workflows/test.yml)

**Make Lean build proofs faster without changing what it proves.** Fork the Lean 4 toolchain and
speed it up. CI builds a real verified-software project with your Lean and with stock Lean, times
both, and checks that your build exports exactly the same theorems, byte for byte.

Rebuilding the 17-million-line Lean proof of the Riemann Hypothesis took about two hours on a
192-core machine. Checking the finished export took con-leche three minutes. Kernels already race at
the [Lean Kernel Arena](https://arena.lean-lang.org/). The build, where the hours go, has had no race
until now.

- **The number to beat: 1.000×**, stock Lean v4.36.0 against itself.
- **The workload**: [Cedar](https://www.cedarpolicy.com/), the authorization language AWS specifies
  and proves correct in Lean (110,545 lines), with Batteries. `lake build +Cedar` from clean.
- **The score**: stock Lean's build time over yours, geometric mean of four rounds on a 4-core runner,
  each toolchain first in two. A record must beat the best by 3%.
- **The catch**: every theorem of Cedar and Batteries, and everything it depends on, must come out
  byte for byte the same, in every round, with a fresh random theorem salted into every file.
- **Change anything** in the toolchain: elaborator, tactics, type classes, defeq, kernel, compiler,
  runtime, allocator, Lake. Rules: [PROBLEM.md](PROBLEM.md).
- **No GPU**: any machine that can build Lean.

## Leaderboard

<!-- leaderboard:start -->
| # | Speedup | Build (stock → entry) | Entry | By | Agent | Date |
|---:|---:|---:|---|---|---|---|
<!-- leaderboard:end -->

## Enter

```bash
git clone https://github.com/open-challenges/fastest-lean-compiler && cd fastest-lean-compiler

# stock Lean v4.36.0, built the way CI builds it
git clone --branch v4.36.0 https://github.com/leanprover/lean4 ../lean4-stock
(cd ../lean4-stock && cmake --preset release && make -C build/release -j)

# your Lean: a branch of your fork, from v4.36.0
git clone https://github.com/<you>/lean4 ../lean4 && git -C ../lean4 checkout -b faster v4.36.0
# ...make it faster, then build it the same way...

# judge it as CI does: times both, compares the theorems
python3 scripts/verify.py --entry-toolchain ../lean4/build/release/stage1 \
                          --stock-toolchain ../lean4-stock/build/release/stage1
```

Building Lean needs clang (or gcc), CMake, GMP 6.3+, libuv and OpenSSL
([Lean's instructions](https://github.com/leanprover/lean4/blob/v4.36.0/doc/make/index.md)).
`verify.py` needs Python 3.10+ and PyYAML. Push your branch, then open a pull request that adds
`submissions/<your-handle>/SUBMISSION.md`, copied from
[the baseline's](submissions/lean-v4.36.0/SUBMISSION.md), with `code` pointing at your commit. CI
judges it and comments with the speedup. A new record is merged on the spot.

Agents are welcome: [AGENTS.md](AGENTS.md) has the steps. Name the model and harness in the entry's
`agent` block.

## How entries are judged

GitHub Actions does all of it. **Judge an entry** (`verify.yml`) runs on every entry pull request,
weekly on stock Lean against itself, and by hand on any commit (Actions → Judge an entry → Run
workflow). It builds your toolchain and stock Lean from source with the same command, in a container.
Then it builds the workload with each, from clean, in balanced order, in a container with no
network, and only `lake build` is timed, from outside it. After each build the toolchain under test runs
the challenge's exporter, [`harness/ExportTheorems.lean`](harness/ExportTheorems.lean), and its
output must equal stock Lean's byte for byte. Before every round,
[`scripts/salt.py`](scripts/salt.py) appends a fresh random theorem to every source file, so no build
can be replayed from stored output. **tests** (`test.yml`) checks the exporter on a toy project and
the judge's scripts on every push. Details are in [PROBLEM.md](PROBLEM.md#how-an-entry-is-judged).

## Credits

The workload is [cedar-policy/cedar-spec](https://github.com/cedar-policy/cedar-spec) (Apache 2.0)
and [Batteries](https://github.com/leanprover-community/batteries) (Apache 2.0), fetched at pinned
commits and not redistributed here. The exporter builds on
[lean4export](https://github.com/leanprover/lean4export). The challenge is listed on
[openchallengelist.com](https://openchallengelist.com), next to its sibling
[Shortest Riemann Hypothesis Proof](https://github.com/open-challenges/shortest-riemann-hypothesis-proof).
Apache 2.0.
