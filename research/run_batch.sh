#!/usr/bin/env bash
set -euo pipefail

notebook="alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
seconds="${1:-180}"
n="${2:-64}"
seed_n="${3:-$n}"
seed_base="${4:-100}"
solver="${5:-research/no_isosceles_search}"

pids=()
for offset in 1 2 3 4 5 6; do
  seed=$((seed_base + offset))
  "$solver" --n "$n" --seed-n "$seed_n" --seconds "$seconds" --seed "$seed" --notebook "$notebook" \
    --out "research/best_n${n}_seed${seed}.txt" \
    >"research/run_n${n}_seed${seed}.log" 2>&1 &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

for offset in 1 2 3 4 5 6; do
  seed=$((seed_base + offset))
  tail -n 1 "research/run_n${n}_seed${seed}.log"
done
exit "$status"
