# Radius-nine frontier around the 164-point `100 x 100` set

Date: 2026-08-27 UTC  
Status: open; the exact `9 -> 10` decision is `UNKNOWN` after a bounded run.

## Question

After the exact result `e_S100(8)=6`, any improvement of the public 164-point
configuration must remove at least nine record points.  The first direct
improvement decision is therefore:

```text
remove exactly 9 record points and add 10 compatible outside points.
```

A positive witness would be a valid 165-point set.  A negative result would
push every improvement to removal radius at least ten.  This run establishes
neither outcome.

## Exact preprocessing

The existing RPC1 and pair-compatibility pipeline was run at radius nine, with
large temporary files kept in `/tmp`:

```text
record points                         164
eligible outside candidates         2,932
minimal link-graph covers          383,184
nonempty forced-pair masks         694,252
candidate pairs tested           4,296,846
compatible pairs                    95,724
incompatible pairs               4,201,122
RPC1 bytes                       31,436,024
pair-cache bytes                  1,087,821
```

The six-thread C++ pair kernel built the exact pair relation in 164.789 s.
The temporary artifacts are reproducible but deliberately not copied to the
nearly full root filesystem.

## Exact bounded search

The audited antichain DFS was reused without changing its semantics.  The full
model includes exact one-, two-, and three-outsider constraints and the safe
greedy-color clique bound.  Its radius-nine `k=10` result is archived in
`radius9_cpp_n100_r9_k10.json`:

```text
status                          UNKNOWN
elapsed seconds                 580.099
DFS nodes                       233,472
family extensions           77,012,633
cover tests              91,148,661,627
masks generated              11,586,185
maximum antichain family            512
removal prunes              76,706,548
color prunes                    26,570
```

`UNKNOWN` is a timeout, not evidence of satisfiability or unsatisfiability.
No proof trace was requested or produced.

An auxiliary `k=7` calibration also remained `UNKNOWN` after 200.048 s
(104,876 nodes and 34,635,776 family extensions), showing that the radius-nine
state space is already substantially harder below the improvement threshold.

## Heuristic search and a useful lower bound

Three deterministic bounded removal-mask searches (300 s, 300 s, and 240 s)
found no `9 -> 10` witness.  Across roughly 8.4 million evaluated masks, all
three reached at most seven individually admissible outsiders and six jointly
compatible outsiders.  This is only search evidence; it is not an upper bound.

One explicit mask and its seven individually admissible outsiders are archived
in `radius9_u7_witness.json`.  The independent direct checker
`radius9_verify_u7.py` verifies every individual extension using exact integer
geometry, then exhausts all 128 subsets of those seven points.  It confirms:

```text
u_S100(9) >= 7
maximum compatible subset among these seven = 6
```

The second statement is local to this one removal mask and outsider list.  It
does not imply `e_S100(9)=6`.  Globally, both `u_S100(9)` and `e_S100(9)` remain
open beyond these lower bounds.

## Reproduction

```bash
research/.venv/bin/python research/radius7_prepare_pair_binary.py \
  --n 100 --radius 9 \
  --output /tmp/radius9_pair_input_n100_r9.bin

g++ -O3 -std=c++20 -fopenmp research/radius7_pair_kernel.cpp \
  -o /tmp/radius9_pair_kernel

OMP_NUM_THREADS=6 /tmp/radius9_pair_kernel \
  /tmp/radius9_pair_input_n100_r9.bin \
  /tmp/radius9_paircompat_n100_r9.json

g++ -O3 -DNDEBUG -std=c++20 \
  research/radius8_cpp_antichain_dfs.cpp \
  -o /tmp/radius9_antichain_dfs

/tmp/radius9_antichain_dfs \
  /tmp/radius9_pair_input_n100_r9.bin \
  /tmp/radius9_paircompat_n100_r9.json \
  10 580 research/radius9_cpp_n100_r9_k10.json

research/.venv/bin/python research/radius9_verify_u7.py \
  research/radius9_u7_witness.json \
  --output research/radius9_u7_witness_verify.json
```

## SHA-256 snapshot

```text
bf3f9cd7f8fa443e45904ec500093b95a36dbfac0d09d15872e98ca7e778c8e2  /tmp/radius9_pair_input_n100_r9.bin
8c09656afe062fff4a24e293cbbb01a70c488bae6893bb057c7dc7996cfb52bd  /tmp/radius9_paircompat_n100_r9.json
26edaed143ff2f3426ae5a92f87c766b5cb7aae92044b84aa20c85b92e5a0bf8  research/radius9_cpp_n100_r9_k10.json
3829813c9faef533fc13c97c0a48323e6a686fa9802250b5aa6ba8b5102900d6  research/radius8_cpp_antichain_dfs.cpp
905c16878dea3e77648d078a8c68c43dc3b95c8a71fefdc42b8e6f2ab077a21a  research/radius7_prepare_pair_binary.py
51c630903373d74d669d7378d55ba46e425ef54ba1ff1a115082a2f3fb104e28  research/radius7_pair_kernel.cpp
ca463e0c546b2a472bb375964d657af5c2c7461a9ebe89aefa5edd08ec9a4d51  research/radius9_u7_witness.json
7d46976afbca905f71decde226bc3db9214830fa83b4e7ec24fab90bd993745a  research/radius9_verify_u7.py
29b3f95ebb30d761146ae98385189f9de4d693a6fcbe238c97420c8a13036aa4  research/radius9_u7_witness_verify.json
```

The root filesystem retained more than 1.2 GB free throughout this run; no
large proof or cache artifact was written there.

## Best next attack

The dominant cost is now clear: more than 91 billion cover tests in ten
minutes.  The most promising exact improvement is to cache, for each full
nine-removal mask, the bitset of outsiders whose minimal cover is contained in
that mask.  This changes repeated per-candidate cover scans into bitset
intersections and can serve both the individual `u(9) >= 10` decision and the
joint `9 -> 10` search.  A second route is a portfolio SAT/CP-SAT attack on the
weaker individual-unlock decision; proving `u_S100(9) < 10` would immediately
reject `9 -> 10`.
