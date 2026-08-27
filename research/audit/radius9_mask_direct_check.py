#!/usr/bin/env python3
"""Direct integer-geometry checker for one radius-nine removal mask.

The checker does not read the RPC1 cover or pair caches.  It reconstructs the
public S100 record, enumerates every point outside the original record, and
tests individual, pair, and outsider-triple compatibility directly from
squared integer distances.
"""

from __future__ import annotations

import argparse
import itertools
import json

from independent_cnf import load_record, squared_distance, validate_record


Point = tuple[int, int]


def parse_removals(text: str) -> list[int]:
    values = [int(item) for item in text.split(",") if item]
    if len(values) != 9 or len(set(values)) != 9:
        raise ValueError("--removals must contain nine distinct record indices")
    return values


def parse_additions(text: str) -> list[Point]:
    if not text:
        return []
    result: list[Point] = []
    for item in text.split(";"):
        x, y = item.split(",")
        result.append((int(x), int(y)))
    return result


def isosceles(a: Point, b: Point, c: Point) -> bool:
    distances = (
        squared_distance(a, b),
        squared_distance(a, c),
        squared_distance(b, c),
    )
    return len(set(distances)) < 3


def analyze(removal_indices: list[int], supplied: list[Point]) -> dict[str, object]:
    record = load_record()
    validate_record(record)
    removed_set = set(removal_indices)
    remaining = [point for index, point in enumerate(record) if index not in removed_set]
    record_set = set(record)

    # Existing distance spectrum at each surviving apex.
    spectra = [
        {squared_distance(apex, other) for other in remaining if other != apex}
        for apex in remaining
    ]

    unlocked: list[Point] = []
    to_base: dict[Point, tuple[int, ...]] = {}
    for x in range(100):
        for y in range(100):
            candidate = (x, y)
            if candidate in record_set:
                continue
            distances = tuple(squared_distance(candidate, point) for point in remaining)
            if len(set(distances)) != len(distances):
                continue
            if any(distance in spectrum for distance, spectrum in zip(distances, spectra)):
                continue
            unlocked.append(candidate)
            to_base[candidate] = distances

    pair_conflicts: list[tuple[Point, Point]] = []
    compatible: dict[Point, set[Point]] = {point: set() for point in unlocked}
    for first, second in itertools.combinations(unlocked, 2):
        cross = squared_distance(first, second)
        allowed = (
            cross not in to_base[first]
            and cross not in to_base[second]
            and all(a != b for a, b in zip(to_base[first], to_base[second]))
        )
        if allowed:
            compatible[first].add(second)
            compatible[second].add(first)
        else:
            pair_conflicts.append((first, second))

    outsider_triples = [
        triple for triple in itertools.combinations(unlocked, 3) if isosceles(*triple)
    ]

    best: tuple[Point, ...] = ()
    for size in range(len(unlocked), -1, -1):
        for choice in itertools.combinations(unlocked, size):
            if any(second not in compatible[first] for first, second in itertools.combinations(choice, 2)):
                continue
            if any(set(triple).issubset(choice) for triple in outsider_triples):
                continue
            best = choice
            break
        if best:
            break

    supplied_valid = False
    if supplied:
        if any(point not in unlocked for point in supplied):
            raise ValueError("a supplied addition is not individually admissible")
        final = remaining + supplied
        if len(final) != len(set(final)):
            raise ValueError("duplicate point in supplied final set")
        validate_record(final)
        supplied_valid = True

    return {
        "method": "direct integer geometry; no RPC1/cache input",
        "removal_indices": removal_indices,
        "removed_points": [record[index] for index in removal_indices],
        "remaining_record_points": len(remaining),
        "individually_unlocked_count": len(unlocked),
        "individually_unlocked": unlocked,
        "pair_conflict_count": len(pair_conflicts),
        "pair_conflicts": pair_conflicts,
        "outsider_isosceles_triple_count": len(outsider_triples),
        "outsider_isosceles_triples": outsider_triples,
        "maximum_simultaneous_additions": len(best),
        "one_maximum_addition_set": best,
        "supplied_additions": supplied,
        "supplied_final_size": len(remaining) + len(supplied),
        "supplied_exchange_valid": supplied_valid,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--removals", required=True)
    parser.add_argument("--additions", default="")
    args = parser.parse_args()
    result = analyze(parse_removals(args.removals), parse_additions(args.additions))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
