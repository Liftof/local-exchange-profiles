#!/usr/bin/env bash
set -euo pipefail

artifact_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$artifact_root"

run_full_radius8=false
if [[ "${1:-}" == "--full-radius8" ]]; then
  run_full_radius8=true
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--full-radius8]" >&2
  exit 2
fi

frontier_tmp_dir="$(mktemp -d /tmp/local-exchange-frontier.XXXXXX)"
trap 'rm -rf -- "$frontier_tmp_dir"' EXIT

echo "[1/5] validate results manifest and frozen artifact hashes"
python3 - "$artifact_root" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "research/RESULTS_MANIFEST.json").read_text())
for relative, expected in manifest["artifact_sha256"].items():
    actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"hash mismatch: {relative}: {actual} != {expected}")
print(f"results_manifest_verified=true artifacts={len(manifest['artifact_sha256'])}")
PY

echo "[2/5] exhaustively check the TAR transition theorem on small models"
python3 research/audit/verify_tar_transition_theorem.py

echo "[3/5] replay the radius-nine individual-unlock witness"
research/.venv/bin/python research/radius9_verify_u7.py \
  research/radius9_u7_witness.json \
  --output "$frontier_tmp_dir/radius9-u7.json"

echo "[4/5] reconstruct the representative mask from integer geometry"
python3 research/audit/radius9_mask_direct_check.py \
  --removals 10,11,18,32,109,117,137,139,140 \
  --additions '95,98;4,98;10,56;89,56;22,99;75,81' \
  > "$frontier_tmp_dir/radius9-direct.json"
python3 - "$frontier_tmp_dir/radius9-direct.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
expected = {
    "individually_unlocked_count": 7,
    "pair_conflict_count": 0,
    "outsider_isosceles_triple_count": 1,
    "maximum_simultaneous_additions": 6,
    "supplied_final_size": 161,
    "supplied_exchange_valid": True,
}
for key, value in expected.items():
    if data.get(key) != value:
        raise SystemExit(f"unexpected {key}: {data.get(key)!r} != {value!r}")
print("radius9_direct_geometry_verified=true unlocked=7 pair_conflicts=0 outsider_triples=1 compatible=6")
PY

echo "[5/5] radius-eight replay policy"
if $run_full_radius8; then
  research/audit/verify_radius8_computation.sh
else
  echo "radius8_full_replay=SKIPPED rerun_with=--full-radius8"
fi

echo "frontier_bundle_verified=true"
