# Certified local profiles for no-isosceles grid sets

This directory is a research artifact for the public AlphaEvolve
isosceles-triangle-free sets of sizes 112 on `64 x 64` and 164 on `100 x 100`.
It computes two local invariants:

- `u_S(r)`: the largest number of outsiders made individually admissible by
  deleting exactly `r` points of `S`;
- `e_S(r)`: the largest number of outsiders that can actually be added
  together after those deletions.

The current exact profiles are

```text
S_100: u(0..6) = 0,0,1,1,2,3,4
       e(0..8) = 0,0,1,1,2,3,4,5,6

S_64:  u(0..7) = 0,1,2,2,4,4,5,6
       e(0..7) = 0,1,2,2,4,4,5,5
```

Every valid `T != S_100` with `|T| >= 164` deletes at least nine record
points. Thus a distinct 164-point set has symmetric difference at least 18,
and an improvement has distance at least 19. Equivalently, under the
symmetric-difference convention used here, the record is 18-swap-optimal
against improvements. This does **not** prove that 164 is globally optimal.

The mandatory deletion transitions strengthen the reconfiguration statement:
every TAR path from `S_100` to a distinct set of size at least 164 visits size
at most 161. Thus no such endpoint is connected to `S_100` inside the TAR
graph restricted to sizes at least 162. In a global search for 165 points, the
valid overlap cut `sum_{s in S_100} x_s <= 155` skips all removal shells zero
through eight.

## Trust status

- The radius-six upper bound `u_100(6) <= 4` has an independently generated
  CNF, a CaDiCaL DRAT proof, and an independent `drat-trim` verification.
- The radius-seven equality `e_100(7)=5` has a directly checked positive
  witness, antichain DFS, an independently regenerated 308,590-clause CNF,
  a 25,282,853-byte CaDiCaL DRAT proof, and independent `drat-trim`
  verification (`s VERIFIED`).
- The radius-eight equality `e_100(8)=6` has a directly checked `8 -> 6`
  witness and an exhaustive C++ antichain rejection of `8 -> 7`. A strictly
  weaker necessary-condition relaxation, with outside-only triples and color
  pruning disabled, is also exhaustively `UNSAT` and was independently
  replayed twice with identical structural counters. There is currently no
  DRAT/LRAT certificate for this radius-eight upper bound.
- The individual-unlock values `u_100(7)` and `u_100(8)` remain open.
- Nothing in this folder has been peer reviewed.

See the manuscript, `EXCHANGE_DFS_METHOD.md`, and the audit reports before
quoting a claim.

`RESULTS_MANIFEST.json` is the machine-readable claim/evidence snapshot. A
single fast command validates its hashes, the transition theorem's finite-model
regression, and both independent radius-nine witness checks:

```bash
research/audit/verify_frontier_bundle.sh
```

Pass `--full-radius8` to append the sanitized differential harness and decisive
radius-eight exhaustive replay.

## Environment

Python 3.12 was used. With `uv`:

```bash
uv venv research/.venv
uv pip install --python research/.venv/bin/python \
  -r research/requirements.txt
```

The source configurations come from the AlphaEvolve notebook pinned at commit
`8f447457957deac61e28bf1676746f0753b3b2f8`; the notebook SHA-256 is
`653accd24369672f1cc757b203dae311f1489895a1cb8e6242d3308fe657891d`.

## Fast checks

```bash
python3 research/verify_robustness.py

research/.venv/bin/python research/radius7_exchange_dfs.py \
  --n 100 --radius 7 --target 6 \
  --pair-cache research/radius7_paircompat_n100_r7.json \
  --seconds 300 --output /tmp/r7-k6.txt

research/.venv/bin/python research/solver_exchange_core_sat.py \
  --n 100 --radius 7 --target 6 \
  --pair-cache research/radius7_paircompat_n100_r7.json \
  --triple-compatibility --symmetry-break --seconds 300 \
  --solver glucose42 --output /tmp/r7-k6-core-sat.txt
```

Expected statuses are `UNSAT` for both radius-seven target-six commands.

The radius-eight C++ reproduction, independent witness check, validation
matrix, counters, and hashes are documented in `radius8_cpp_REPORT.md`. Its
decisive upper-bound run targets seven additions after eight removals; the next
possible record-improvement frontier is radius nine, targeting ten additions.
The complete frozen check and replay is:

```bash
research/audit/verify_radius8_computation.sh
```

Add `--full-input-audit` to regenerate all 2,036 candidates, 150,848 covers,
331,300 forced masks, and 2,071,630 pair decisions (several minutes).

The first radius-nine attack is documented in `radius9_FRONTIER.md`. Its exact
`9 -> 10` run ended `UNKNOWN`, and three bounded heuristics found no improving
witness; neither fact is an impossibility result. A direct integer-geometry
witness does establish `u_100(9) >= 7`. On that mask the seven outsiders are
pairwise compatible, but one all-outsider isosceles triple reduces the largest
compatible subset of the list to six. Recheck it with:

```bash
research/.venv/bin/python research/radius9_verify_u7.py \
  research/radius9_u7_witness.json \
  --output /tmp/radius9_u7_witness_verify.json
```

The transition-sensitive TAR theorem also has a finite-model regression that
checks every hereditary family on ground sets of size at most four, every base
set, and every endpoint/radius pair:

```bash
python3 research/audit/verify_tar_transition_theorem.py
```

The expected final line reports `tar_transition_theorem_small_models_verified=true`
with 197 families, 1,439 base sets, and 44,056 assertions. This is a systematic
edge-case check, not a replacement for the human proof.

## Full radius-six certificate replay

The replay checks hashes, 9,099 elementary matching witnesses, and the
291,778,586-byte DRAT trace. It takes several minutes:

```bash
research/audit/verify_certificate.sh
```

The required output contains `s VERIFIED`. See `audit/proof_manifest.json` for
the exact hashes and tool commits.
