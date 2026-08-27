#!/usr/bin/env python3
"""Write compact cover/forced-mask input for the C++ pair kernel."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from radius7_pair_compatibility import build_required_masks
from solve_removal_radius_cpsat import enumerate_minimal_covers
from solver_exchange_sat import build_conflicts, load_record


def words(mask: int) -> tuple[int, int, int]:
    return mask & ((1 << 64) - 1), (mask >> 64) & ((1 << 64) - 1), mask >> 128


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(64, 100), default=100)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    record = load_record(args.n)
    outside, conflicts, _ = build_conflicts(record, args.n)
    candidates = []
    covers = []
    for outside_index, edges in enumerate(conflicts):
        family = enumerate_minimal_covers(edges, args.radius)
        if family:
            candidates.append(outside[outside_index])
            covers.append([sum(1 << vertex for vertex in cover) for cover in family])
    required = build_required_masks(record, candidates)
    digest = hashlib.sha256(repr(record).encode()).hexdigest().encode("ascii")

    with args.output.open("wb") as stream:
        stream.write(struct.pack("<4sIIII64s", b"RPC1", args.n, args.radius, len(record), len(candidates), digest))
        for (x, y), family in zip(candidates, covers):
            stream.write(struct.pack("<HHI", x, y, len(family)))
            for mask in family:
                stream.write(struct.pack("<QQQ", *words(mask)))
        stream.write(struct.pack("<I", len(required)))
        for (a, b), mask in sorted(required.items()):
            stream.write(struct.pack("<IIQQQ", a, b, *words(mask)))
    print(
        f"candidates={len(candidates)} covers={sum(map(len, covers))} "
        f"forced_pairs={len(required)} bytes={args.output.stat().st_size} output={args.output}"
    )


if __name__ == "__main__":
    main()
