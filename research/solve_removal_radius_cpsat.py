#!/usr/bin/env python3
"""Exact CP-SAT upper bound for additions after deleting r record points."""

import argparse
import ast
import json
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"


def load_record(n=100, record_json=None):
    if record_json is not None:
        payload = json.loads(Path(record_json).read_text())
        source_n = int(payload["n"])
        if source_n != n:
            raise ValueError(f"record n={source_n} does not match requested n={n}")
        record = [tuple(map(int, point)) for point in payload["points"]]
        if len(record) != len(set(record)):
            raise ValueError("record contains duplicate points")
        if not all(0 <= x < n and 0 <= y < n for x, y in record):
            raise ValueError("record contains a point outside the n by n grid")
        return record
    notebook = json.loads(NOTEBOOK.read_text())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    tail = source.split(f"sol_{n} = ", 1)[1]
    return ast.literal_eval(tail[: tail.index("]") + 1])


def build_conflicts(record, n=100):
    points = np.asarray(record, dtype=np.int32)
    selected = set(record)
    pair_i, pair_j = np.triu_indices(len(record), 1)
    differences = points[pair_i] - points[pair_j]
    pair_distance = np.sum(differences * differences, axis=1)
    outside = [(x, y) for x in range(n) for y in range(n) if (x, y) not in selected]
    conflicts = []
    total_edges = 0
    for point in outside:
        delta = points - np.asarray(point, dtype=np.int32)
        distance = np.sum(delta * delta, axis=1)
        mask = (
            (distance[pair_i] == distance[pair_j])
            | (distance[pair_i] == pair_distance)
            | (distance[pair_j] == pair_distance)
        )
        edges = np.column_stack((pair_i[mask], pair_j[mask])).astype(np.int16)
        conflicts.append(edges)
        total_edges += len(edges)
    return outside, conflicts, total_edges


def matching_lower_bound(edges):
    used = set()
    matching = 0
    for a, b in edges:
        a, b = int(a), int(b)
        if a not in used and b not in used:
            used.add(a)
            used.add(b)
            matching += 1
    return matching


def minimize_cover(cover, edges):
    cover = set(cover)
    changed = True
    while changed:
        changed = False
        for vertex in tuple(cover):
            reduced = cover - {vertex}
            if all(int(a) in reduced or int(b) in reduced for a, b in edges):
                cover = reduced
                changed = True
                break
    return tuple(sorted(cover))


def enumerate_minimal_covers(edges_array, budget):
    edges = tuple((int(a), int(b)) for a, b in edges_array)
    results = set()

    def recurse(remaining, chosen, left):
        if not remaining:
            results.add(minimize_cover(chosen, edges))
            return
        if left == 0 or matching_lower_bound(remaining) > left:
            return
        degree = {}
        for a, b in remaining:
            degree[a] = degree.get(a, 0) + 1
            degree[b] = degree.get(b, 0) + 1
        a, b = max(remaining, key=lambda edge: degree[edge[0]] + degree[edge[1]])
        for vertex in (a, b):
            recurse(
                tuple(edge for edge in remaining if vertex not in edge),
                chosen + (vertex,),
                left - 1,
            )

    recurse(edges, (), budget)
    return sorted(cover for cover in results if len(cover) <= budget)


def solve(n, radius, target, cover_dnf, seconds, workers, output, record_json=None):
    record = load_record(n, record_json)
    outside, conflicts, total_edges = build_conflicts(record, n)

    model = cp_model.CpModel()
    removed = [model.new_bool_var(f"remove_{i}") for i in range(len(record))]
    unlocked = [model.new_bool_var(f"unlock_{i}") for i in range(len(outside))]
    model.add(sum(removed) == radius)
    total_minimal_covers = 0
    candidates_with_covers = 0
    all_cover_active = []
    for candidate_index, edges in enumerate(conflicts):
        candidate = unlocked[candidate_index]
        if cover_dnf:
            covers = enumerate_minimal_covers(edges, radius)
            if not covers:
                model.add(candidate == 0)
                continue
            candidates_with_covers += 1
            total_minimal_covers += len(covers)
            cover_active = []
            for cover_index, cover in enumerate(covers):
                active = model.new_bool_var(f"cover_{candidate_index}_{cover_index}")
                for vertex in cover:
                    model.add_implication(active, removed[vertex])
                model.add(active >= sum(removed[vertex] for vertex in cover) - len(cover) + 1)
                model.add_implication(active, candidate)
                cover_active.append(active)
                all_cover_active.append(active)
            model.add_bool_or(cover_active).only_enforce_if(candidate)
        else:
            for a, b in edges:
                model.add(candidate <= removed[int(a)] + removed[int(b)])
            matching_vertices = []
            used = set()
            for a, b in edges:
                a, b = int(a), int(b)
                if a not in used and b not in used:
                    used.add(a)
                    used.add(b)
                    matching_vertices.extend((a, b))
            if matching_vertices:
                model.add(
                    sum(removed[index] for index in matching_vertices)
                    >= (len(matching_vertices) // 2) * candidate
                )
    if target:
        model.add(sum(unlocked) >= target)
    else:
        model.maximize(sum(unlocked))
    if target and cover_dnf:
        model.add_decision_strategy(
            unlocked,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MAX_VALUE,
        )
        model.add_decision_strategy(
            all_cover_active,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MAX_VALUE,
        )
    model.add_decision_strategy(
        removed,
        cp_model.CHOOSE_FIRST,
        cp_model.SELECT_MAX_VALUE,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = False
    solver.parameters.search_branching = cp_model.FIXED_SEARCH
    status = solver.solve(model)
    status_name = solver.status_name(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        output.write_text(
            "\n".join(
                [
                    f"n={n}",
                    f"record_size={len(record)}",
                    f"radius={radius}",
                    f"target_unlocked={target}",
                    f"outside_candidates={len(outside)}",
                    f"conflict_edges={total_edges}",
                    f"cover_dnf={cover_dnf}",
                    f"candidates_with_covers={candidates_with_covers}",
                    f"minimal_covers={total_minimal_covers}",
                    f"status={status_name}",
                    f"best_bound_unlocked={solver.best_objective_bound}",
                    f"wall_time_seconds={solver.wall_time:.6f}",
                ]
            )
            + "\n"
        )
        print(f"status={status_name} radius={radius} output={output}")
        return

    chosen_removals = [record[i] for i, variable in enumerate(removed) if solver.value(variable)]
    chosen_unlocked = [outside[i] for i, variable in enumerate(unlocked) if solver.value(variable)]
    objective = len(chosen_unlocked) if target else int(round(solver.objective_value))
    best_bound = int(round(solver.best_objective_bound))

    # Independent evaluation of the returned assignment.
    removal_indices = {i for i, variable in enumerate(removed) if solver.value(variable)}
    independently_unlocked = []
    for point, edges in zip(outside, conflicts):
        if all(int(a) in removal_indices or int(b) in removal_indices for a, b in edges):
            independently_unlocked.append(point)
    assert independently_unlocked == chosen_unlocked
    assert objective == len(chosen_unlocked)

    lines = [
        f"n={n}",
        f"record_size={len(record)}",
        f"radius={radius}",
        f"target_unlocked={target}",
        f"outside_candidates={len(outside)}",
        f"conflict_edges={total_edges}",
        f"cover_dnf={cover_dnf}",
        f"candidates_with_covers={candidates_with_covers}",
        f"minimal_covers={total_minimal_covers}",
        f"status={status_name}",
        f"objective_unlocked={objective}",
        f"best_bound_unlocked={best_bound}",
        f"wall_time_seconds={solver.wall_time:.6f}",
        f"removals={chosen_removals}",
        f"unlocked={chosen_unlocked}",
    ]
    output.write_text("\n".join(lines) + "\n")
    print(
        f"status={status_name} radius={radius} objective={objective} "
        f"best_bound={best_bound} conflicts={total_edges} output={output}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--record-json", type=Path)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--target", type=int, default=0)
    parser.add_argument("--cover-dnf", action="store_true")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    solve(
        args.n,
        args.radius,
        args.target,
        args.cover_dnf,
        args.seconds,
        args.workers,
        args.output,
        args.record_json,
    )


if __name__ == "__main__":
    main()
