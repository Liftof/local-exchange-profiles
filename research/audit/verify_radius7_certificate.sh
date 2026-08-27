#!/usr/bin/env bash
set -euo pipefail

audit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd -- "${audit_dir}/../.." && pwd)"
cd "${root_dir}"

sha256sum -c research/audit/radius7_certificate_checksums.sha256

PYTHONPATH=research/audit python3 \
  research/audit/verify_radius7_witness.py \
  research/radius7_dfs_n100_r7_k5.txt

PYTHONPATH=research/audit timeout 300s python3 \
  research/audit/radius7_pair_cache_independent.py \
  research/radius7_paircompat_n100_r7.json

PYTHONPATH=research/audit timeout 120s python3 \
  research/audit/radius7_core_independent.py \
  research/radius7_paircompat_n100_r7.json --target 6

set +e
checker_output="$(
  timeout 120s research/audit/tools/drat-trim/drat-trim \
    research/audit/radius7_core_r7_k6_nosym.cnf \
    research/audit/radius7_core_r7_k6_nosym.drat 2>&1
)"
checker_status=$?
set -e
printf '%s\n' "${checker_output}"

if [[ ${checker_status} -ne 0 ]]; then
  printf 'radius-7 proof verification failed: checker exit %d\n' "${checker_status}" >&2
  exit 1
fi
if ! printf '%s\n' "${checker_output}" | tr '\r' '\n' | grep -qx 's VERIFIED'; then
  printf 'radius-7 proof verification failed: exact success line absent\n' >&2
  exit 1
fi

printf 'radius7_certificate_bundle_verified=true\n'
