import Export

/-!
# Export a workload's theorems

    export-theorems <root module>... -- <package prefix>... > theorems.ndjson

Imports the root modules from the `.olean` files a build wrote, and prints in Lean's NDJSON export
format (lean4export) every theorem declared in a module whose first name component is one of the
prefixes (`Cedar`, `Batteries`, ...), in name order, together with every constant those theorems
depend on: the definitions their statements talk about, the lemmas their proofs use, down to `Init`.

Theorems only, because they are the verified output of a build. The elaborator, tactics and the rest
of the toolchain are not part of it: an entry may change them freely, as long as every theorem comes
out the same. There is no metadata line, since it would name the toolchain's git hash.

Nothing here is trusted. The judge builds this exporter with each toolchain it times and runs it on
that toolchain's own build, then compares the bytes with what stock Lean's build gives.
-/

open Lean

def main (args : List String) : IO UInt32 := do
  let (roots, rest) := args.span (· != "--")
  let prefixes := rest.drop 1
  if roots.isEmpty || prefixes.isEmpty then
    IO.eprintln "usage: export-theorems <root module>... -- <package prefix>..."
    return 2
  initSearchPath (← findSysroot)
  let env ← importModules (roots.toArray.map fun r => { module := r.toName }) {}
  let mut theorems : Array Name := #[]
  for (n, ci) in env.constants do
    if let .thmInfo _ := ci then
      if let some idx := env.getModuleIdxFor? n then
        if prefixes.contains (env.header.moduleNames[idx.toNat]!).getRoot.toString then
          theorems := theorems.push n
  theorems := theorems.qsort Name.lt
  IO.eprintln s!"[export] {theorems.size} theorems in modules under {prefixes}"
  M.run env do
    initState env []
    for c in theorems do
      modify fun st => { st with noMDataExprs := {} }
      dumpConstant c
  return 0
