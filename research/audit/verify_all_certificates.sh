#!/usr/bin/env bash
set -euo pipefail

audit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"${audit_dir}/verify_certificate.sh"
"${audit_dir}/verify_radius7_certificate.sh"

printf 'radius6_and_radius7_certificate_bundles_verified=true\n'
