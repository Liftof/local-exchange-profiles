# Exact radius-eight exchange profile for the 164-point `100 x 100` set

Date: 2026-08-27 UTC  
Status: exhaustive computational result; independently replayed, but no formal
proof trace (DRAT/LRAT) is currently available for the radius-eight upper bound.

## Result

Let `S100` be the public 164-point isosceles-triangle-free set in the
AlphaEvolve problem repository, and let

```text
e_S(r) = max {|A| : there are R subset S and A subset (grid \ S),
                       |R| = r, and (S \ R) union A is valid}.
```

The computation in this directory establishes

```text
e_S100(8) = 6.
```

The lower bound is the `8 -> 6` witness in
`radius8_cpp_n100_r8_k6.json`.  A separate Python program enumerates every
triple in the resulting 162-point set using exact integer squared distances;
its result is in `radius8_cpp_n100_r8_k6_verify.json`.

The upper bound is the exhaustive `8 -> 7` rejection in
`radius8_cpp_n100_r8_k7.json`.  More strongly,
`radius8_cpp_n100_r8_k7_relaxed_nocolor.json` rejects the necessary-condition
relaxation obtained by:

1. deleting all constraints on triples made of three outside points; and
2. disabling the greedy-color clique upper bound.

That relaxed run returned `UNSAT` after 78,031 DFS nodes, 10,009,190 family
extensions, and 5,388,204,289 cover-containment/union tests.  Because every
genuine exchange is feasible in the relaxation, its `UNSAT` result proves the
upper bound without relying on either all-outsider geometry code or color
pruning.

Together with the previously determined radii zero through seven, the exact
profile is now

```text
e_S100(0..8) = (0, 0, 1, 1, 2, 3, 4, 5, 6).
```

Consequently, any valid set `T != S100` with `|T| >= 164` removes at least nine
points of `S100`.  Thus:

- a distinct valid 164-point set has symmetric difference at least 18;
- any valid set of at least 165 points has symmetric difference at least 19;
- a direct improvement search around this record must begin at removal radius
  at least nine (`9 -> 10` is the next decision frontier).

These are local statements around the published 164-point configuration.  They
do not prove that 164 is globally optimal.

## Exact recurrence

For every eligible outside point `p`, the RPC1 input stores the inclusion-
minimal vertex covers `C(p)` of its one-outsider link graph.  For two outside
points `p,q`, `F(p,q)` is the mask of record vertices forced to be removed by
mixed triples containing `p` and `q`.

At a search node with selected outsiders `X`, the solver carries precisely the
antichain `A_X` of inclusion-minimal record-removal masks supporting `X`.  On
adding `q`, it computes

```text
A_(X union {q}) = min_subset {
    M union C union (union over p in X of F(p,q)) :
    M in A_X, C in C(q), and popcount(the union) <= r
}.
```

An empty family is an exact rejection.  Candidates are enumerated canonically
in a deterministic reversed smallest-last (degeneracy) order.  The pair graph
is an exact necessary filter.  In the full build, outside-only isosceles
triples are filtered by precomputed exact-integer bitsets.  A greedy coloring
of the remaining pair graph supplies only a safe clique upper bound.

The main C++ optimization does not change the recurrence: once a partial mask
already has cardinality `r`, a cover can be added iff it is a subset of that
mask.  The resulting mask is unchanged, avoiding billions of materialized
unions.

## Validation and audit

Regression against the independently certified radius-seven result:

- `r=7,k=5`: `SAT`, with the same known witness, then direct cubic geometry
  verification;
- `r=7,k=6`: `UNSAT` in the full solver;
- `r=7,k=6`, no outside triples and no color pruning: `UNSAT` after exactly
  15,239 nodes, matching the earlier Python relaxation.

The C++ source also completed an AddressSanitizer + UndefinedBehaviorSanitizer
radius-seven rejection with no diagnostic.  The independently written checker
`audit/radius8_cpp_inputs_independent.py` regenerated the canonical record
geometry, all 2,036 eligible candidates, all 150,848 minimal covers, all
331,300 nonempty forced-pair masks, and all 2,071,630 pair decisions.  It
matched the 35,950 positive pairs in the cache exactly; the compact result is
`radius8_cpp_input_audit.json`.  A separate randomized sanitizer harness,
`audit/radius8_cpp_unit_harness.cpp`, checked 5,000 antichain extensions and
1,400 coloring instances against brute-force references; its archived result
is `radius8_cpp_unit_audit.txt`.

The decisive no-triples/no-color `r=8,k=7` run was independently recompiled
and replayed twice.  Both replays returned `UNSAT` with the same structural
counters (78,031 nodes, 10,009,190 family extensions, 5,388,204,289 cover
tests); only wall time differed.

The negative result remains an exhaustive-program computation, not a
proof-assistant theorem or proof-trace-certified SAT result.  Publication
language should therefore say “exact exhaustive computation, independently
cross-checked,” not “formally verified.”

## Reproduction

Run from the project root.  Executables and temporary radius-seven input are
placed on temporary storage.

The frozen checksums, independent witness verifier, sanitizer unit harness,
recompilation, decisive relaxed search, and deterministic-counter comparison
are wrapped by:

```bash
research/audit/verify_radius8_computation.sh
```

Use `--full-input-audit` to additionally regenerate every candidate, minimal
cover, forced mask, and pair decision.  The individual commands are retained
below for inspection.

```bash
g++ -O3 -DNDEBUG -std=c++20 \
  research/radius8_cpp_antichain_dfs.cpp \
  -o /tmp/radius8_cpp_solver

/tmp/radius8_cpp_solver \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json \
  6 120 research/radius8_cpp_n100_r8_k6.json

research/.venv/bin/python research/radius8_cpp_verify.py \
  research/radius8_cpp_n100_r8_k6.json \
  --output research/radius8_cpp_n100_r8_k6_verify.json

/tmp/radius8_cpp_solver \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json \
  7 120 research/radius8_cpp_n100_r8_k7.json

g++ -O3 -DNDEBUG -std=c++20 \
  -DR8CPP_RELAX_OUTSIDE_TRIPLES -DR8CPP_NO_COLOR_PRUNING \
  research/radius8_cpp_antichain_dfs.cpp \
  -o /tmp/radius8_cpp_solver_relaxed

/tmp/radius8_cpp_solver_relaxed \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json \
  7 600 research/radius8_cpp_n100_r8_k7_relaxed_nocolor.json

research/.venv/bin/python \
  research/audit/radius8_cpp_inputs_independent.py \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json \
  --workers 6 --rows-per-task 16 \
  --output /tmp/radius8_cpp_input_audit_replay.json

g++ -O1 -g -std=c++20 -Wall -Wextra -Wpedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  research/audit/radius8_cpp_unit_harness.cpp \
  -o /tmp/radius8_cpp_unit_harness

ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1 \
  /tmp/radius8_cpp_unit_harness
```

Exit codes are `10` for `SAT`, `20` for `UNSAT`, and `0` for a bounded
`UNKNOWN` timeout.  Runtime varies with host load and is not part of the
mathematical claim.

## Core hashes

```text
3829813c9faef533fc13c97c0a48323e6a686fa9802250b5aa6ba8b5102900d6  radius8_cpp_antichain_dfs.cpp
f6ae5a6e6d873718a6c7ca7f4ca94c58fdfcdf007b15ac99dd5bb4fae10fb5b6  radius8_cpp_verify.py
31d4606f6f878ce6ddf4fc9cb48fbaeecd4380b11b478c456ec5ea2e040f295e  radius7_pair_input_n100_r8.bin
30e257b34af3a05a193023e3005fd46a933794fcd4ce429812b540724fe784d7  radius7_paircompat_n100_r8.json
d20223f380e8391ebd708e9c0376ea6f94440c806b8f384e56382ab8f47060e8  radius8_cpp_n100_r8_k6.json
243d66ed97cdf822bf1e887b75308a1fab72419974d6569c2f296206631c5b5a  radius8_cpp_n100_r8_k6_verify.json
d1e5955b28f0a845e8fd00f748a7870c5a92fd91ea75c4bdc8c8cb47e02281d6  radius8_cpp_n100_r8_k7.json
ff5bb9771663ea239e7dfa6c6f6b0e8c1a4697d6d135e850e77b85467968fbab  radius8_cpp_n100_r8_k7_relaxed_nocolor.json
4264586e20211a9b88c628e6192897dde035f770d1124dabdb8829e0e3ec3e92  audit/radius8_cpp_inputs_independent.py
b06a8eabb366fde4b60f12e88d9a27c636e4dd24523821af0ab09f0ccfde9340  radius8_cpp_input_audit.json
17a51584d6cde095f1aa70230c18e8e222fee2bb50be5aba5c44c1e14f076a9f  audit/radius8_cpp_unit_harness.cpp
d6e5d4915156859281f2d5f9552eec7fc93f93a9edeaf9ae82aa714ebb43abea  radius8_cpp_unit_audit.txt
```
