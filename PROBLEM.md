---
spec: problem.md/v1
name: Fastest Lean Compiler
tagline: Make the Lean 4 toolchain build proofs faster. CI times your Lean against stock Lean on a verified-software workload; every theorem must stay byte-identical.
status: active
domain: formal-methods
tags: [lean4, formal-verification, compilers, build-performance, theorem-proving, verified-software]
compute: cpu
compute_details: "No GPU. Building Lean from source takes about 35 minutes on CI's 4-core runner (2 CPU-hours), and the workload then builds in under three minutes with stock Lean (about two on a 10-core laptop). Any Linux or macOS machine with 16 GB of memory and 20 GB of disk will do for development."
deadline: rolling
prizes: recognition only
organizer:
  name: Open Challenge List
  url: https://openchallengelist.com
website: https://github.com/open-challenges/fastest-lean-compiler
leaderboard: https://github.com/open-challenges/fastest-lean-compiler#leaderboard

tracks:
  - id: cedar
    name: "Cedar: same theorems, less time"
    metric: speedup
    unit: "× stock Lean"
    direction: maximize
    baseline: 1.0
    description: Stock Lean v4.36.0's time to build the Cedar workload from clean, divided by your toolchain's, on CI's 4-core runner, geometric mean of four salted rounds, each toolchain first in two. Every theorem of Cedar and Batteries, with everything it depends on, must come out byte for byte the same as stock Lean's.

submit:
  how: pull-request
  path: submissions/<handle>/
  format: Only SUBMISSION.md. Its code field pins a commit of your public fork of leanprover/lean4, based on v4.36.0.
  requirements: [a C/C++ toolchain (clang), CMake, GMP 6.3 or newer, libuv, OpenSSL, git, Python 3.10+]
  verification: CI builds your toolchain and stock Lean v4.36.0 from source in a container, then times both building the Cedar workload, with no network, in alternating rounds, each round with a fresh random theorem appended to every source file. Your build must export the same theorems as stock Lean's, byte for byte. Only the workload's build is timed, from outside the container.
  eligibility: Open to everyone.
  cost: free
  agents: welcome
  attribution: Name the model and harness in the agent block of SUBMISSION.md.

quickstart: |
  git clone https://github.com/open-challenges/fastest-lean-compiler && cd fastest-lean-compiler
  git clone --branch v4.36.0 https://github.com/leanprover/lean4 ../lean4-stock
  (cd ../lean4-stock && cmake --preset release && make -C build/release -j)   # stock Lean, built as CI builds it
  git clone https://github.com/leanprover/lean4 ../lean4 && git -C ../lean4 checkout -b faster v4.36.0
  # ... make Lean faster in ../lean4, build it the same way, then judge it as CI does:
  python3 scripts/verify.py --entry-toolchain ../lean4/build/release/stage1 --stock-toolchain ../lean4-stock/build/release/stage1
---

# Fastest Lean Compiler

Lean checks the biggest proofs people have ever written, and building them has become the slow part.
When Levent Alpöge released his Lean proof of the Riemann Hypothesis on 20 November 2026 (17.4
million lines in 175,187 modules), independent checkers raced to confirm it. Rebuilding it from
source took about two hours on a rented 192-core machine. Another verifier needed 128 GB of memory,
1.2 TB of disk and about 500 core-hours. Even the 76,000-line compact rewrite takes one to two hours
on 12 cores. Checking the finished proof is fast by comparison: once it was built and exported,
con-leche replayed all of it in 3 minutes 15 seconds on 64 threads.

Kernels already have a race: the [Lean Kernel Arena](https://arena.lean-lang.org/) ranks 38
independent checkers, and the fastest needs 31 times less CPU time than Lean's own to check
Mathlib. Nobody races the build: the elaborator, tactics, type class resolution, the kernel inside it, the code generator,
the runtime and Lake. Every hour there is paid again by everyone who wants to check a proof. The
Lean FRO cut the instructions for a Mathlib build by 23.6% in v4.37.0-rc1 alone, so there is plenty
left to find.

**Make Lean build proofs faster without changing what it proves.**

## The task

Fork [leanprover/lean4](https://github.com/leanprover/lean4) at **v4.36.0** (`611c117`) and change
anything you like: the elaborator, `simp`, `omega`, type class resolution, definitional equality
checking, the kernel, the compiler, the runtime and its allocator, Lake's scheduling. CI builds your
toolchain from source exactly as it builds stock Lean, with
`cmake --preset release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++` and then `make`, and
times both on the workload.

### The workload

[Cedar](https://www.cedarpolicy.com/), the authorization policy language that AWS specifies and
proves correct in Lean: `cedar-policy/cedar-spec` at `0e8c45c`, folder `cedar-lean`, with its
dependency [Batteries](https://github.com/leanprover-community/batteries) at `v4.36.0` (`b4b25a3`).
The timed command is `lake build +Cedar`, from a clean build folder: 304 files and 110,545 lines of
Cedar (its semantics, validator, symbolic compiler and their proofs), plus the Batteries modules they
import. It needs no Mathlib, so a whole judgement fits on a free CI runner.
[`bench/workload.json`](bench/workload.json) pins all of it.

### The score: speedup over stock Lean

```
speedup = geometric mean over rounds of  (stock Lean's build time) / (your build time)
```

CI runs four rounds on one machine (GitHub's `ubuntu-24.04` runner: 4 cores, 16 GB), and each
toolchain goes first in two of them: on that runner the second build of a round came out up to 4%
faster than the first, and balancing the order cancels that. Each toolchain first builds the
workload once untimed, and before each timed build pending disk writes are flushed and both
toolchains are read into memory. Only `lake build` is timed, by the judge,
outside the sandbox. Building your toolchain is not timed. The score is wall-clock time against stock
Lean in the same job on the same machine, because GitHub's runners expose no hardware instruction
counters. Stock Lean scores 1.000 against itself ([the baseline](submissions/lean-v4.36.0/SUBMISSION.md)),
give or take the runner's noise, which is why **a new record must beat the best speedup so far by 3%**.

### Same theorems, byte for byte

A faster build counts only if it proves the same things. After each timed build, the toolchain under
test builds and runs the challenge's exporter,
[`harness/ExportTheorems.lean`](harness/ExportTheorems.lean). It prints, in Lean's NDJSON export
format ([lean4export](https://github.com/leanprover/lean4export)), every theorem declared in Cedar
and Batteries, together with everything those theorems depend on: the definitions their statements
mention and the lemmas their proofs use, down to `Init`. The export from your build must be
**identical to stock Lean's, byte for byte**, in every round.

So statements, definitions and proof terms must all come out exactly as stock Lean elaborates them.
The elaborator's own code, Lean's compiler, Lake and the rest of the toolchain are not in the
export: change them as much as you like. What you cannot change is the result. A different `simp`
strategy that finds a different proof does not qualify, even if the kernel would accept it. Stock
Lean's export was itself checked by Lean's kernel during its build.

### The salt

Before each round the judge appends one fresh theorem to every source file of the workload, Cedar's
and Batteries' alike: `theorem flcSalt_<random> : Nat.add a b = c := rfl`, with random numbers.
Both toolchains build the same salted sources, and the salt shows up in both exports. Every file is
new in every round, so no toolchain can pass by replaying stored output.

## Rules

- **No special-casing the workload.** Your toolchain must not recognize Cedar, Batteries, their
  files, modules or declarations, or the salt, and must not contain or fetch output built from
  them. General-purpose speedups only: anything that would also speed up Mathlib.
- **No network, no state between builds.** Each workload build starts from a clean copy, in a
  container with no network that can write only its own folder. Reading or writing anything outside
  it, or keeping state between rounds, is against the rules even where the sandbox would not stop
  it. Building the toolchain has the network only because Lean's build fetches its pinned
  dependencies (CaDiCaL, mimalloc, leantar); fetching anything else there is against the rules.
- **Deterministic output.** Two builds of the same sources must export the same bytes, as stock
  Lean's do. Parallelism is welcome as long as the result does not depend on timing.
- **Limits.** Your toolchain must build within 150 minutes, and the workload within 60, on the CI
  runner.
- **Review.** CI shows every entry's diff against v4.36.0. An entry that changes binary files,
  `stage0` (the bootstrap compiler), more than 20,000 lines or more than 5,000 in one file, adds a
  download to the build files, or whose added lines mention the workload, waits for a maintainer,
  who merges it once the diff has been read. Maintainers remove entries that break these rules,
  whatever the judge said.
- Ties go to the earlier entry.

## How to submit

1. Fork [leanprover/lean4](https://github.com/leanprover/lean4) and make your changes on a branch
   from `v4.36.0`. Push it, and note the full commit hash.
2. Judge it locally, as CI will: build stock v4.36.0 and your branch the same way, then run
   `python3 scripts/verify.py --entry-toolchain <yours>/build/release/stage1 --stock-toolchain <stock>/build/release/stage1`.
   Or build both in Docker, as CI does: `python3 scripts/verify.py --code https://github.com/<you>/lean4/tree/<commit> --sandbox docker`.
3. Add `submissions/<your-handle>/SUBMISSION.md` (or `submissions/<your-handle>-<name>/` for
   another entry) in a pull request that changes nothing else, starting from
   [the baseline's](submissions/lean-v4.36.0/SUBMISSION.md): `code` is
   `https://github.com/<you>/lean4/tree/<full commit hash>`, `author` is your GitHub handle, and the
   `agent` block names the model and harness, if one did the work. Say in the text what you changed
   and why it is faster.
4. CI judges the commit, which takes about two hours, and comments with the speedup. A
   new record is merged at once, unless its diff raised a flag (see Review). The leaderboard shows
   CI's measurement, never a number from the entry.

## How an entry is judged

[`.github/workflows/verify.yml`](.github/workflows/verify.yml), with
[`scripts/verify.py`](scripts/verify.py):

1. **Fetch.** Your commit and stock Lean's, and the diff between them.
2. **Build both toolchains** from source with the same command, each in a container with no
   capabilities and a read-only root, where the build can write only its own source tree (and reach
   the network, for Lean's pinned dependencies).
3. **Build the exporter** with each toolchain.
4. **Rounds.** Four of them, each toolchain first in two. For each round, a fresh salted copy of the
   workload per toolchain; `lake build +Cedar` in the container, timed outside it; then the exports,
   compared byte for byte.
5. **Score**: the geometric mean of stock's time over yours across the rounds.

The weekly run judges stock Lean against itself, which keeps an eye on the runner's noise and on the
pins.

## Ideas

Some places people have found time recently (none of them is guaranteed to keep the output the
same, which is the hard part):

- Lean v4.37.0-rc1's release notes list Mathlib build speedups: type class resolution (#15889:
  2.7% wall-clock, 6.7% less time in type class resolution), importing (#14362: 36% less time
  importing during the build), and the compiler (#16153, #16148: 3.7% and 1.8% fewer instructions).
  Porting them to v4.36.0 is fair game if the theorems stay the same.
- On Andrew Sutherland's verification page, Lean's kernel replayed the 17-million-line RH proof
  in 9 hours instead of 48 with one allocator setting (`MIMALLOC_GENERIC_COLLECT` in the run script).
- One independent rebuild of the RH proof found Lake's setup overhead and failed `statx` calls from
  the search path order costing real time on a 192-core machine.
- Independent kernels such as nano-lean, gruszka and con-leche check Mathlib many times faster
  than Lean's kernel in the Lean Kernel Arena. Lean's own kernel is part of every build.
