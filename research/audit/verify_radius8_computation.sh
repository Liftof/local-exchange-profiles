#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"

task_tmp="$(mktemp -d)"
trap 'rm -rf -- "$task_tmp"' EXIT

echo "[1/5] frozen artifact checksums"
sha256sum -c research/radius8_cpp_checksums.sha256

echo "[2/5] independent exact-integer witness check"
research/.venv/bin/python research/audit/verify_exchange_witness.py \
  research/radius8_exchange_n100_r8_k6_witness.txt

echo "[3/5] randomized antichain/coloring tests under ASan+UBSan"
g++ -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -std=c++20 research/audit/radius8_cpp_unit_harness.cpp \
  -o "$task_tmp/r8-unit"
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1 \
  "$task_tmp/r8-unit"

echo "[4/5] rebuild and replay decisive relaxed r=8,k=7 search"
g++ -O3 -DNDEBUG -DR8CPP_RELAX_OUTSIDE_TRIPLES \
  -DR8CPP_NO_COLOR_PRUNING -std=c++20 -Wall -Wextra -Wpedantic \
  research/radius8_cpp_antichain_dfs.cpp -o "$task_tmp/r8-relaxed"

set +e
"$task_tmp/r8-relaxed" \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json \
  7 160 "$task_tmp/r8-k7-relaxed.json"
solver_status=$?
set -e
if [[ "$solver_status" -ne 20 ]]; then
  echo "expected solver exit 20 (UNSAT), got $solver_status" >&2
  exit 1
fi

echo "[5/5] compare all deterministic result fields"
research/.venv/bin/python - \
  research/radius8_cpp_n100_r8_k7_relaxed_nocolor.json \
  "$task_tmp/r8-k7-relaxed.json" <<'PY'
import json
import sys

expected_path, replay_path = sys.argv[1:]
with open(expected_path, encoding="utf-8") as handle:
    expected = json.load(handle)
with open(replay_path, encoding="utf-8") as handle:
    replay = json.load(handle)
expected.pop("elapsed_seconds", None)
replay.pop("elapsed_seconds", None)
if replay != expected:
    raise SystemExit("replay differs from archived deterministic fields")
print(
    "radius8_replay_verified=true "
    f"status={replay['status']} nodes={replay['nodes']} "
    f"extensions={replay['family_extensions']}"
)
PY

if [[ "${1:-}" == "--full-input-audit" ]]; then
  echo "[optional] independently regenerate all candidates, covers, masks, and pairs"
  research/.venv/bin/python research/audit/radius8_cpp_inputs_independent.py \
    research/radius7_pair_input_n100_r8.bin \
    research/radius7_paircompat_n100_r8.json \
    --workers "${R8_AUDIT_WORKERS:-4}" --rows-per-task 8 \
    --output "$task_tmp/radius8_cpp_input_audit.json"
  research/.venv/bin/python - "$task_tmp/radius8_cpp_input_audit.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    result = json.load(handle)
expected = {
    "status": "VERIFIED",
    "eligible_candidates": 2036,
    "minimal_covers": 150848,
    "forced_pair_masks_nonempty": 331300,
    "forced_record_entries": 397808,
    "pairs_tested": 2071630,
    "compatible_pairs": 35950,
}
for key, value in expected.items():
    if result.get(key) != value:
        raise SystemExit(f"input audit mismatch for {key}: {result.get(key)!r}")
print("radius8_full_input_audit_verified=true")
PY
fi

echo "radius8_computation_verified=true"
