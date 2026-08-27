#!/usr/bin/env bash
set -euo pipefail

audit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd -- "${audit_dir}/../.." && pwd)"
cd "${root_dir}"

sha256sum -c research/audit/certificate_checksums.sha256
python3 research/audit/verify_matching_certificate.py \
  research/audit/r6_matching_witnesses.json

set +e
checker_output="$(
  timeout 600s research/audit/tools/drat-trim/drat-trim \
    research/audit/r6_t5_matching.cnf \
    research/audit/r6_t5_matching.drat 2>&1
)"
checker_status=$?
set -e
printf '%s\n' "${checker_output}"

if [[ ${checker_status} -ne 0 ]]; then
  printf 'certificate verification failed: checker exit %d\n' "${checker_status}" >&2
  exit 1
fi
if ! printf '%s\n' "${checker_output}" | tr '\r' '\n' | grep -qx 's VERIFIED'; then
  printf 'certificate verification failed: exact success line absent\n' >&2
  exit 1
fi

printf 'certificate_bundle_verified=true\n'
