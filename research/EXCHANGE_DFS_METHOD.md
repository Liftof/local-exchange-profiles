# Exact local-exchange certification by removal-mask antichains

Working method note, 27 August 2026. The computational claims below have not
yet been peer reviewed.

## Generic 3-uniform-hypergraph formulation

Let `H=(V,E)` be a 3-uniform hypergraph, let `S` be an independent set, and put
`O=V\S`. For a fixed removal radius `r` and every `p in O`, define:

- `L_S(p)`, the graph on `S` whose edges are the pairs `{a,b}` such that
  `{p,a,b}` is a hyperedge of `H`;
- `C_r(p)`, the family of inclusion-minimal vertex covers of `L_S(p)` having
  size at most `r`;
- `F_S(p,q)={s in S : {p,q,s} in E}`.

For `A subset O`, assume first that `A` contains no hyperedge of `H`. Then there
is an `R subset S`, `|R|<=r`, for which `(S\R) union A` is independent if and
only if one can choose a cover `C_p in C_r(p)` for every `p in A` such that

```text
| union_{p in A} C_p  union  union_{{p,q} subset A} F_S(p,q) | <= r.       (1)
```

Necessity follows by classifying every forbidden triple by its number of
vertices in `O`: one outsider gives a vertex-cover constraint, two outsiders
force the remaining point of `S` to be removed, and three outsiders are
forbidden inside `A`. Conversely, these three conditions eliminate every
possible hyperedge in `(S\R) union A`. If the union in (1) has fewer than `r`
points, it can be padded to exactly `r`, since further deletions preserve
independence.

## Exact antichain recurrence

Let `M_r(A)` be the inclusion-minimal masks realizing the union in (1). Start
with

```text
M_r(empty) = {empty}.
```

When adding `p` to `A`, reject the branch if `A union {p}` contains an
all-outsider hyperedge. Otherwise compute

```text
M_r(A union {p}) = minimal_by_inclusion {
    M union C union (union_{q in A} F_S(p,q)) :
    M in M_r(A), C in C_r(p), |...| <= r
}.
```

Discarding a strict superset mask is exact: every later union feasible from the
superset is also feasible from its subset. Consequently `M_r(A)` is nonempty
if and only if `A` is simultaneously addable after at most `r` deletions.
A canonical increasing-index DFS enumerates every candidate set once.

The implementation also uses the exact pair-compatibility graph. A pair is an
edge exactly when its two-cover recurrence is nonempty. Searching for `k`
additions may therefore be restricted to the `(k-1)`-core, because every
`K_k` lies in that core. This is only a safe prefilter; the common-mask
antichain, not pairwise compatibility alone, establishes feasibility.

## Certified results

For the published 164-point `100 x 100` AlphaEvolve construction:

```text
e_S(0..7) = (0, 0, 1, 1, 2, 3, 4, 5).
```

At radius seven, a five-point compatible addition exists, while six points are
impossible. Thus `e_S(7)=5`. In particular:

- every distinct valid 164-point set removes at least eight record points, so
  its symmetric difference from the record is at least 16;
- every valid set of at least 165 points removes at least eight record points,
  so its symmetric difference from the record is at least 17.

The radius-seven witness is:

```text
remove = [(92,51),(96,97),(7,51),(8,93),(26,40),(73,40),(77,95)]
add    = [(95,98),(89,56),(75,81),(10,56),(77,99)]
```

For the published 112-point `64 x 64` construction:

```text
u_S(0..7) = (0, 1, 2, 2, 4, 4, 5, 6)
e_S(0..7) = (0, 1, 2, 2, 4, 4, 5, 5).
```

Hence the individual-unlock and genuine-exchange profiles first separate at
radius seven: `e_S(7)=5 < u_S(7)=6`. With

```text
B_f(R) = max_{0 <= r < R} (r - f(r)),
```

this gives `B_e(8)=2`, whereas `B_u(8)=1`. The genuine exchange profile
therefore detects a two-point reconfiguration valley that the individual
unlock profile misses.

## Open radius-eight frontier on `100 x 100`

The decision `e_S(8) >= 9` would produce a new 165-point construction. It is
not resolved in this run. The exact preprocessing reached:

```text
eligible candidates             2,036
minimal covers                 150,848
pairs tested                 2,071,630
exact compatible pairs          35,950
8-core vertices                    736
8-core edges                     33,474
```

The original Python pair loop was stopped at about 280 seconds before writing
an artifact. A bounded C++ bit-mask kernel computed the same exact relation in
25.74 seconds on six threads. On radius seven, its complete payload (apart
from the runtime field) was byte-for-byte-equivalent after JSON parsing to the
independent Python pair computation: 1,324 candidates and 11,942 compatible
pairs.

Three distinct exact attempts at `r=8,k=9` remain `UNKNOWN`:

- full exchange SAT: 300.18 seconds, 2,294,947 clauses;
- antichain DFS: 309.97 seconds, 24,576 nodes and 4,200,088 family extensions;
- 8-core SAT: 300.09 seconds, 408,653 clauses.

No 165-point witness was found. A separately generated and directly verified
radius-eight exchange with six additions proves only `e_S(8) >= 6`; it has
final size 162. Neither the timeouts nor that lower bound establish the value
of `e_S(8)`.

## Two computational routes

1. `radius7_exchange_dfs.py` implements the exact antichain recurrence. For
   `n=100,r=7`, it finds `k=5` and rejects `k=6` after 15,227 DFS nodes.
2. `solver_exchange_core_sat.py` separately encodes the one-, two-, and
   three-outsider constraints, while sharing the geometric and cover
   preprocessing with the DFS. For `n=100,r=7,k=6`, the exact pair graph's
   5-core has 392 vertices and 11,054 edges. Exact triple preprocessing adds
   200,796 ternary incompatibility clauses. Glucose 4.2 returns `UNSAT` in
   14.53 seconds after a 19.25-second build.
3. Every returned positive construction is checked by direct enumeration of
   all point triples, separately from the search recurrence.

Independent standard-library audit programs regenerate all 1,324 eligible
candidates, 55,528 covers, 875,826 pair decisions, the 392-vertex 5-core, and
all 200,796 ternary no-goods exactly. The resulting no-symmetry CNF has 308,590
clauses. CaDiCaL returns `UNSAT` and emits a 25,282,853-byte DRAT trace (SHA-256
`6a845c1af080a63661599f9633910b170293502c9319688cf55829ca1ba37c3b`);
`drat-trim` independently returns `s VERIFIED` in 26.669 seconds.

The unpruned SAT encoding remains `UNKNOWN` at 300 seconds. It is not used as
evidence for the theorem.

## Reproduction commands

Run from the project root:

```bash
research/.venv/bin/python research/radius7_pair_compatibility.py \
  --n 100 --radius 7 --workers 4 --rows-per-task 12 \
  --output research/radius7_paircompat_n100_r7.json

research/.venv/bin/python research/radius7_exchange_dfs.py \
  --n 100 --radius 7 --target 5 \
  --pair-cache research/radius7_paircompat_n100_r7.json \
  --seconds 300 --output research/radius7_dfs_n100_r7_k5.txt

research/.venv/bin/python research/radius7_exchange_dfs.py \
  --n 100 --radius 7 --target 6 \
  --pair-cache research/radius7_paircompat_n100_r7.json \
  --seconds 300 --output research/radius7_dfs_n100_r7_k6.txt

research/.venv/bin/python research/solver_exchange_core_sat.py \
  --n 100 --radius 7 --target 6 \
  --pair-cache research/radius7_paircompat_n100_r7.json \
  --triple-compatibility --symmetry-break --seconds 300 \
  --solver glucose42 --output research/radius7_core_sat_n100_r7_k6.txt

research/.venv/bin/python research/radius7_prepare_pair_binary.py \
  --n 100 --radius 8 --output research/radius7_pair_input_n100_r8.bin

g++ -O3 -std=c++20 -fopenmp research/radius7_pair_kernel.cpp \
  -o /tmp/radius7_pair_kernel

OMP_NUM_THREADS=6 /tmp/radius7_pair_kernel \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json
```

Environment used: Python 3.12.12, NumPy 2.5.2, python-sat 1.9.dev15.

## SHA-256 snapshot

```text
4f3fa9da709b8afdf1e3112264389c72400f6eb4481e208409f0c1b32e284257  radius7_exchange_dfs.py
810ded93a526da10cb731b667790886fe791bdbb16f05b023370f39192575ca1  radius7_pair_compatibility.py
cf0407ebfc4102de3aeeaf640f5cb74956c571dc6c5aa34d22c631cb57c88f9d  solver_exchange_core_sat.py
ceb308448dde48c205fa7ca9c8a1c9a2c382b84da993d09d1fe5dc7bf055dca1  radius7_paircompat_n100_r7.json
2916f41b98b46bc4a9640e7bd21490aeae73efc8aefdf4a7f86a37f1f5534eff  radius7_dfs_n100_r7_k5.txt
a3a60ab59d081b28f19519cf6241199b4c5fa3997bb552deed9ddeebfe87c0b2  radius7_dfs_n100_r7_k6.txt
80c9237644e181e118c760808eafee95d33ca2d09e3e3937a11a8de679c6b4b6  radius7_core_sat_n100_r7_k6.txt
905c16878dea3e77648d078a8c68c43dc3b95c8a71fefdc42b8e6f2ab077a21a  radius7_prepare_pair_binary.py
51c630903373d74d669d7378d55ba46e425ef54ba1ff1a115082a2f3fb104e28  radius7_pair_kernel.cpp
31d4606f6f878ce6ddf4fc9cb48fbaeecd4380b11b478c456ec5ea2e040f295e  radius7_pair_input_n100_r8.bin
30e257b34af3a05a193023e3005fd46a933794fcd4ce429812b540724fe784d7  radius7_paircompat_n100_r8.json
1db5e666f9d492aee8b614d9d9c30f3bb4d361d6f437d52a4aa43851042ddd66  radius7_dfs_n100_r8_k9.txt
5796dff8a4169fb1d7fb8e34871ee8aa3e622437c5705b2092d80ffdab7fb161  radius7_core_sat_n100_r8_k9.txt
270da628d0c3ddd711c761fe92d56da985e1d959bdb4cd5e3a05316d6527dfe0  radius7_exchange_sat_n100_r8_k9.txt
653accd24369672f1cc757b203dae311f1489895a1cb8e6242d3308fe657891d  source AlphaEvolve notebook
```

These hashes describe this run's snapshot. Recompute them after any source or
artifact change.
