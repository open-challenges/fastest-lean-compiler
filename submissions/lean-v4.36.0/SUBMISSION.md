---
spec: submission.md/v1
problem: ../../PROBLEM.md
title: Stock Lean v4.36.0
author: leanprover
date: 2026-11-16
baseline: true

code: https://github.com/leanprover/lean4/tree/611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9
---

# Stock Lean v4.36.0

The starting point, not an entry of its own: Lean v4.36.0, released 16 November 2026, commit
`611c117`, built from source the way CI builds every entry. Judged against itself, it measures the
runner's noise, which is why a record must beat the best speedup by 3%.

## Reproduce

```bash
python3 scripts/verify.py --code stock --sandbox docker
```
