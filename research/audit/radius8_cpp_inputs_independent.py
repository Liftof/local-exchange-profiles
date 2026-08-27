#!/usr/bin/env python3
"""Independent audit of the RPC1 input and pair cache used by the C++ DFS.

This checker deliberately imports no production radius-7/radius-8 module.  It
uses the earlier standard-library geometry and alternative vertex-cover
enumerator from ``independent_cnf.py``, parses RPC1 itself, recomputes every
mixed-triple forced mask directly from the three squared side lengths, and
checks every candidate pair against the JSON compatibility cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import struct
import time
from pathlib import Path

from independent_cnf import (
    alternative_minimal_covers,
    build_conflicts,
    load_record,
    squared_distance,
    validate_record,
)


_CANDIDATES: list[tuple[int, int]] = []
_COVERS: list[tuple[int, ...]] = []
_COVER_SETS: list[frozenset[int]] = []
_DISTANCES: list[tuple[int, ...]] = []
_FORCED_BINARY: dict[tuple[int, int], int] = {}
_CACHED_PAIRS: frozenset[tuple[int, int]] = frozenset()
_RADIUS = 0


def parse_rpc1(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    position = 0

    def take(fmt: str) -> tuple[object, ...]:
        nonlocal position
        size = struct.calcsize(fmt)
        if position + size > len(raw):
            raise ValueError("truncated RPC1 input")
        values = struct.unpack_from(fmt, raw, position)
        position += size
        return values

    magic, n, radius, record_size, candidate_count, digest = take("<4sIIII64s")
    if magic != b"RPC1":
        raise ValueError("bad RPC1 magic")
    candidates: list[tuple[int, int]] = []
    covers: list[tuple[int, ...]] = []
    unused_mask = ~((1 << int(record_size)) - 1)
    for _ in range(int(candidate_count)):
        x, y, count = take("<HHI")
        family: list[int] = []
        for _ in range(int(count)):
            low, middle, high = take("<QQQ")
            mask = int(low) | (int(middle) << 64) | (int(high) << 128)
            if mask & unused_mask:
                raise ValueError("cover contains a bit outside the record")
            if mask.bit_count() > int(radius):
                raise ValueError("cover exceeds the removal radius")
            family.append(mask)
        if len(family) != len(set(family)):
            raise ValueError("duplicate cover in RPC1 family")
        candidates.append((int(x), int(y)))
        covers.append(tuple(family))
    (forced_count,) = take("<I")
    forced: dict[tuple[int, int], int] = {}
    for _ in range(int(forced_count)):
        left, right, low, middle, high = take("<IIQQQ")
        key = (int(left), int(right))
        mask = int(low) | (int(middle) << 64) | (int(high) << 128)
        if not (0 <= key[0] < key[1] < int(candidate_count)):
            raise ValueError("invalid forced-pair indices")
        if key in forced:
            raise ValueError("duplicate forced-pair entry")
        if mask == 0:
            raise ValueError("redundant zero forced-pair entry")
        if mask & unused_mask:
            raise ValueError("forced mask contains a bit outside the record")
        forced[key] = mask
    if position != len(raw):
        raise ValueError("trailing RPC1 data")
    return {
        "raw": raw,
        "n": int(n),
        "radius": int(radius),
        "record_size": int(record_size),
        "candidate_count": int(candidate_count),
        "digest": bytes(digest).decode("ascii"),
        "candidates": candidates,
        "covers": covers,
        "forced": forced,
    }


def direct_forced_mask(left_index: int, right_index: int) -> int:
    left = _CANDIDATES[left_index]
    right = _CANDIDATES[right_index]
    outside_distance = squared_distance(left, right)
    mask = 0
    for record_index, (left_distance, right_distance) in enumerate(
        zip(_DISTANCES[left_index], _DISTANCES[right_index])
    ):
        if (
            left_distance == right_distance
            or left_distance == outside_distance
            or right_distance == outside_distance
        ):
            mask |= 1 << record_index
    return mask


def compatible(left_index: int, right_index: int, forced: int) -> bool:
    """Direct semantics, with two elementary exact short cuts."""
    if forced.bit_count() > _RADIUS:
        return False
    left = _COVERS[left_index]
    right = _COVERS[right_index]
    if not forced and min(map(int.bit_count, left)) + min(map(int.bit_count, right)) <= _RADIUS:
        return True
    if all(mask.bit_count() == _RADIUS for mask in left) and all(
        mask.bit_count() == _RADIUS for mask in right
    ):
        common = _COVER_SETS[left_index] & _COVER_SETS[right_index]
        return any((mask | forced) == mask for mask in common)
    if len(left) > len(right):
        left, right = right, left
    for first in left:
        partial = first | forced
        if partial.bit_count() > _RADIUS:
            continue
        for second in right:
            if (partial | second).bit_count() <= _RADIUS:
                return True
    return False


def check_rows(bounds: tuple[int, int]) -> dict[str, object]:
    start, stop = bounds
    tested = compatible_count = forced_nonempty = forced_entries = 0
    forced_mismatches: list[tuple[int, int, int, int]] = []
    pair_mismatches: list[tuple[int, int, bool, bool]] = []
    for left in range(start, stop):
        for right in range(left + 1, len(_CANDIDATES)):
            forced = direct_forced_mask(left, right)
            binary_forced = _FORCED_BINARY.get((left, right), 0)
            if forced != binary_forced and len(forced_mismatches) < 5:
                forced_mismatches.append((left, right, forced, binary_forced))
            if forced:
                forced_nonempty += 1
                forced_entries += forced.bit_count()
            expected = compatible(left, right, forced)
            cached = (left, right) in _CACHED_PAIRS
            if expected != cached and len(pair_mismatches) < 5:
                pair_mismatches.append((left, right, expected, cached))
            compatible_count += expected
            tested += 1
    return {
        "tested": tested,
        "compatible": compatible_count,
        "forced_nonempty": forced_nonempty,
        "forced_entries": forced_entries,
        "forced_mismatches": forced_mismatches,
        "pair_mismatches": pair_mismatches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rows-per-task", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()

    parsed = parse_rpc1(args.binary)
    if parsed["n"] != 100 or parsed["record_size"] != 164:
        raise ValueError("audit is pinned to the 100 by 100, 164-point record")
    record = load_record()
    validate_record(record)
    digest = hashlib.sha256(repr(record).encode()).hexdigest()
    if parsed["digest"] != digest:
        raise AssertionError("RPC1 record digest mismatch")

    outside, conflicts = build_conflicts(record)
    independent_candidates: list[tuple[int, int]] = []
    independent_covers: list[tuple[int, ...]] = []
    for point, edges in zip(outside, conflicts):
        family = alternative_minimal_covers(edges, int(parsed["radius"]))
        if family:
            independent_candidates.append(point)
            independent_covers.append(
                tuple(sorted(sum(1 << vertex for vertex in cover) for cover in family))
            )
    if independent_candidates != parsed["candidates"]:
        raise AssertionError("independently regenerated candidate list differs from RPC1")
    binary_covers = [tuple(sorted(family)) for family in parsed["covers"]]
    if independent_covers != binary_covers:
        for index, (expected, actual) in enumerate(zip(independent_covers, binary_covers)):
            if expected != actual:
                raise AssertionError(
                    f"RPC1 cover family differs at candidate {index}: "
                    f"missing={sorted(set(expected)-set(actual))[:3]} "
                    f"extra={sorted(set(actual)-set(expected))[:3]}"
                )
        raise AssertionError("RPC1 cover-family list length differs")

    cache_raw = args.cache.read_bytes()
    cache = json.loads(cache_raw)
    if (
        cache.get("format") != "radius-pair-compatibility-v1"
        or cache["n"] != parsed["n"]
        or cache["radius"] != parsed["radius"]
        or cache["record_size"] != parsed["record_size"]
        or cache["record_sha256"] != digest
        or [tuple(point) for point in cache["eligible_candidates"]] != independent_candidates
    ):
        raise AssertionError("pair-cache metadata or candidates differ")
    cached_pair_list = [tuple(map(int, pair)) for pair in cache["compatible_pairs"]]
    if len(cached_pair_list) != len(set(cached_pair_list)):
        raise AssertionError("duplicate cached compatible pair")
    if any(not (0 <= left < right < len(independent_candidates)) for left, right in cached_pair_list):
        raise AssertionError("cached compatible pair out of range or out of order")
    if len(cached_pair_list) != cache["compatible_pair_count"]:
        raise AssertionError("cached compatible-pair count differs")

    global _CANDIDATES, _COVERS, _COVER_SETS, _DISTANCES
    global _FORCED_BINARY, _CACHED_PAIRS, _RADIUS
    _CANDIDATES = independent_candidates
    _COVERS = independent_covers
    _COVER_SETS = [frozenset(family) for family in independent_covers]
    _DISTANCES = [
        tuple(squared_distance(candidate, record_point) for record_point in record)
        for candidate in independent_candidates
    ]
    _FORCED_BINARY = parsed["forced"]  # type: ignore[assignment]
    _CACHED_PAIRS = frozenset(cached_pair_list)
    _RADIUS = int(parsed["radius"])

    bounds = [
        (start, min(start + args.rows_per_task, len(_CANDIDATES)))
        for start in range(0, len(_CANDIDATES), args.rows_per_task)
    ]
    totals = {
        "tested": 0,
        "compatible": 0,
        "forced_nonempty": 0,
        "forced_entries": 0,
    }
    forced_mismatches: list[object] = []
    pair_mismatches: list[object] = []
    context = mp.get_context("fork")
    with context.Pool(args.workers) as pool:
        for part in pool.imap_unordered(check_rows, bounds):
            for key in totals:
                totals[key] += int(part[key])
            forced_mismatches.extend(part["forced_mismatches"])
            pair_mismatches.extend(part["pair_mismatches"])
    if forced_mismatches:
        raise AssertionError(f"forced-mask mismatch examples: {forced_mismatches[:5]}")
    if pair_mismatches:
        raise AssertionError(f"pair-cache mismatch examples: {pair_mismatches[:5]}")
    expected_pairs = len(_CANDIDATES) * (len(_CANDIDATES) - 1) // 2
    if totals["tested"] != expected_pairs or totals["compatible"] != len(_CACHED_PAIRS):
        raise AssertionError("independent pair totals differ")
    if len(_FORCED_BINARY) != totals["forced_nonempty"]:
        raise AssertionError("RPC1 forced-pair entry count differs")

    result = {
        "status": "VERIFIED",
        "binary": str(args.binary),
        "binary_sha256": hashlib.sha256(parsed["raw"]).hexdigest(),
        "cache": str(args.cache),
        "cache_sha256": hashlib.sha256(cache_raw).hexdigest(),
        "record_size": len(record),
        "radius": _RADIUS,
        "eligible_candidates": len(_CANDIDATES),
        "minimal_covers": sum(map(len, _COVERS)),
        "forced_pair_masks_nonempty": totals["forced_nonempty"],
        "forced_record_entries": totals["forced_entries"],
        "pairs_tested": totals["tested"],
        "compatible_pairs": totals["compatible"],
        "workers": args.workers,
        "elapsed_seconds": time.monotonic() - started,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
