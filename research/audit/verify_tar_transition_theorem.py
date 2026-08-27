#!/usr/bin/env python3
"""Exhaustively check the transition-sensitive TAR bound on small universes.

This is not a proof of the theorem.  It is an independent finite-model check
covering every hereditary family on ground sets of size at most four, every
choice of base set, and every reachable endpoint/radius pair.
"""

from __future__ import annotations

import heapq


def is_downset(family_mask: int, n: int) -> bool:
    for subset in range(1 << n):
        if not (family_mask >> subset) & 1:
            continue
        for bit in range(n):
            if subset & (1 << bit):
                if not (family_mask >> (subset ^ (1 << bit))) & 1:
                    return False
    return True


def profile(family_mask: int, n: int, base: int) -> tuple[list[int], list[int]]:
    base_size = base.bit_count()
    outside = ((1 << n) - 1) ^ base
    u = [0] * (base_size + 1)
    e = [0] * (base_size + 1)
    removed_subsets = [r for r in range(1 << n) if r & ~base == 0]
    outsider_subsets = [a for a in range(1 << n) if a & ~outside == 0]

    for removed in removed_subsets:
        radius = removed.bit_count()
        retained = base ^ removed
        individually = 0
        for bit in range(n):
            point = 1 << bit
            if outside & point and (family_mask >> (retained | point)) & 1:
                individually += 1
        u[radius] = max(u[radius], individually)

        compatible = max(
            addition.bit_count()
            for addition in outsider_subsets
            if (family_mask >> (retained | addition)) & 1
        )
        e[radius] = max(e[radius], compatible)
    return u, e


def widest_bottlenecks(family_mask: int, n: int, source: int) -> list[int]:
    """Maximum possible minimum cardinality on a TAR path from source."""
    count = 1 << n
    best = [-1] * count
    best[source] = source.bit_count()
    queue = [(-best[source], source)]
    while queue:
        neg_value, state = heapq.heappop(queue)
        value = -neg_value
        if value != best[state]:
            continue
        for bit in range(n):
            neighbor = state ^ (1 << bit)
            if not (family_mask >> neighbor) & 1:
                continue
            candidate = min(value, neighbor.bit_count())
            if candidate > best[neighbor]:
                best[neighbor] = candidate
                heapq.heappush(queue, (-candidate, neighbor))
    return best


def check(n: int) -> tuple[int, int, int]:
    subset_count = 1 << n
    family_count = 0
    base_count = 0
    assertions = 0
    for family_mask in range(1 << subset_count):
        if not is_downset(family_mask, n):
            continue
        family_count += 1
        for base in range(subset_count):
            if not (family_mask >> base) & 1:
                continue
            base_count += 1
            u, e = profile(family_mask, n, base)
            assert all(e[r] <= u[r] for r in range(len(e)))
            widest = widest_bottlenecks(family_mask, n, base)
            m = base.bit_count()
            for target in range(subset_count):
                if not (family_mask >> target) & 1:
                    continue
                removed = (base & ~target).bit_count()
                for radius in range(1, removed + 1):
                    du = max(0, max(r + 1 - u[r] for r in range(radius)))
                    de = max(0, max(r + 1 - e[r] for r in range(radius)))
                    assert de >= du
                    assert widest[target] <= m - du
                    assert widest[target] <= m - de
                    assertions += 4
    return family_count, base_count, assertions


def main() -> None:
    total_families = 0
    total_bases = 0
    total_assertions = 0
    for n in range(1, 5):
        families, bases, assertions = check(n)
        total_families += families
        total_bases += bases
        total_assertions += assertions
        print(
            f"n={n} hereditary_families={families} "
            f"base_sets={bases} assertions={assertions}"
        )
    print(
        "tar_transition_theorem_small_models_verified=true "
        f"families={total_families} base_sets={total_bases} "
        f"assertions={total_assertions}"
    )


if __name__ == "__main__":
    main()
