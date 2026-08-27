#!/usr/bin/env python3
"""Independent direct verifier for a radius8_cpp_antichain_dfs SAT witness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from solver_exchange_sat import load_record, verify_no_isosceles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.result.read_text())
    if result.get("format") != "radius8-cpp-antichain-dfs-v1":
        raise ValueError("unexpected result format")
    if result.get("status") != "SAT":
        raise ValueError("only SAT results contain a witness")

    n = int(result["n"])
    radius = int(result["radius_removed"])
    target = int(result["target_added"])
    record = load_record(n)
    expected_digest = hashlib.sha256(repr(record).encode()).hexdigest()
    if result["input_record_sha256"] != expected_digest:
        raise AssertionError("record digest mismatch")

    removals = [int(index) for index in result["removal_indices"]]
    additions = [tuple(map(int, point)) for point in result["additions"]]
    if len(removals) != radius or len(set(removals)) != radius:
        raise AssertionError("wrong or duplicate removal indices")
    if any(index < 0 or index >= len(record) for index in removals):
        raise AssertionError("removal index out of range")
    if len(additions) != target or len(set(additions)) != target:
        raise AssertionError("wrong or duplicate additions")
    if any(not (0 <= x < n and 0 <= y < n) for x, y in additions):
        raise AssertionError("addition outside the grid")
    if set(additions) & set(record):
        raise AssertionError("addition is already in the record")

    removed = set(removals)
    final = [point for index, point in enumerate(record) if index not in removed] + additions
    verified = (
        len(final) == len(record) - radius + target
        and len(set(final)) == len(final)
        and verify_no_isosceles(final)
    )
    if not verified:
        raise AssertionError("direct cubic integer-geometry verification failed")

    payload = {
        "format": "radius8-cpp-independent-witness-verification-v1",
        "result": str(args.result),
        "result_sha256": hashlib.sha256(args.result.read_bytes()).hexdigest(),
        "record_sha256": expected_digest,
        "radius_removed": radius,
        "target_added": target,
        "final_size": len(final),
        "direct_cubic_integer_geometry_verified": True,
        "removals": [record[index] for index in removals],
        "additions": additions,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"verified=true radius={radius} target={target} "
        f"final_size={len(final)} output={args.output}"
    )


if __name__ == "__main__":
    main()
