#!/usr/bin/env bash
set -euo pipefail

notebook="alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
seconds="${1:-300}"
solver="${2:-research/no_isosceles_search_next}"
seed_base="${3:-300}"

pids=()
for offset in 1 2 3 4 5 6; do
  seed=$((seed_base + offset))
  "$solver" --n 100 --seconds "$seconds" --seed "$seed" --symmetric 1 --notebook "$notebook" \
    --out "research/best_sym_n100_seed${seed}.txt" \
    >"research/run_sym_n100_seed${seed}.log" 2>&1 &
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
  tail -n 1 "research/run_sym_n100_seed${seed}.log"
done
exit "$status"
