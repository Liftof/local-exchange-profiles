#!/usr/bin/env python3
"""Independent audit of the radius-7 pair-compatibility cache.

No production radius-7 module is imported.  One-outsider conflicts and minimal
covers come from the earlier independent standard-library implementation.  The
record points forced by a pair of outsiders are recomputed directly from the
three squared side lengths for every candidate pair and every record point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from independent_cnf import (
    alternative_minimal_covers,
    build_conflicts,
    load_record,
    squared_distance,
    validate_record,
)


def direct_forced_mask(
    left: tuple[int, int],
    right: tuple[int, int],
    left_distances: list[int],
    right_distances: list[int],
) -> int:
    outside_distance = squared_distance(left, right)
    mask = 0
    for record_index, (left_distance, right_distance) in enumerate(
        zip(left_distances, right_distances)
    ):
        if (
            left_distance == right_distance
            or left_distance == outside_distance
            or right_distance == outside_distance
        ):
            mask |= 1 << record_index
    return mask


def compatible(left_covers: list[int], right_covers: list[int], forced: int, radius: int) -> bool:
    if forced.bit_count() > radius:
        return False
    if len(left_covers) > len(right_covers):
        left_covers, right_covers = right_covers, left_covers
    for left in left_covers:
        partial = left | forced
        if partial.bit_count() > radius:
            continue
        for right in right_covers:
            if (partial | right).bit_count() <= radius:
                return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    started = time.monotonic()

    cache_raw = args.cache.read_bytes()
    cache = json.loads(cache_raw)
    radius = cache["radius"]
    if cache["n"] != 100 or radius != 7:
        raise ValueError("this independent audit is pinned to n=100, radius=7")

    record = load_record()
    validate_record(record)
    outside, conflicts = build_conflicts(record)
    candidates: list[tuple[int, int]] = []
    cover_masks: list[list[int]] = []
    for point, edges in zip(outside, conflicts):
        covers = alternative_minimal_covers(edges, radius)
        if covers:
            candidates.append(point)
            cover_masks.append(
                [sum(1 << vertex for vertex in cover) for cover in sorted(covers)]
            )

    cached_candidates = [tuple(point) for point in cache["eligible_candidates"]]
    if candidates != cached_candidates:
        raise AssertionError("independently regenerated eligible candidate list differs")

    distances = [
        [squared_distance(candidate, record_point) for record_point in record]
        for candidate in candidates
    ]
    independent_pairs: list[tuple[int, int]] = []
    forced_nonempty = 0
    forced_entries = 0
    tested = 0
    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            forced = direct_forced_mask(
                left,
                right,
                distances[left_index],
                distances[right_index],
            )
            if forced:
                forced_nonempty += 1
                forced_entries += forced.bit_count()
            if compatible(
                cover_masks[left_index],
                cover_masks[right_index],
                forced,
                radius,
            ):
                independent_pairs.append((left_index, right_index))
            tested += 1

    cached_pairs = [tuple(pair) for pair in cache["compatible_pairs"]]
    if independent_pairs != cached_pairs:
        independent_set = set(independent_pairs)
        cached_set = set(cached_pairs)
        raise AssertionError(
            "pair cache differs: "
            f"missing={sorted(independent_set - cached_set)[:5]} "
            f"extra={sorted(cached_set - independent_set)[:5]}"
        )

    result = {
        "status": "VERIFIED",
        "cache": str(args.cache),
        "cache_sha256": hashlib.sha256(cache_raw).hexdigest(),
        "record_size": len(record),
        "eligible_candidates": len(candidates),
        "minimal_covers": sum(map(len, cover_masks)),
        "pairs_tested": tested,
        "compatible_pairs": len(independent_pairs),
        "forced_pair_masks_nonempty": forced_nonempty,
        "forced_record_entries": forced_entries,
        "elapsed_seconds": time.monotonic() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
