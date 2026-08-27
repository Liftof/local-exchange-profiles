#!/usr/bin/env bash
set -euo pipefail

solver="research/no_isosceles_deep"
notebook="alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
seconds="${1:-300}"

pids=()
for seed in 701 702 703 704 705 706; do
  "$solver" --n 100 --seconds "$seconds" --seed "$seed" --deep 1 --notebook "$notebook" \
    --out "research/deep_n100_seed${seed}.txt" \
    >"research/deep_n100_seed${seed}.log" 2>&1 &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

for seed in 701 702 703 704 705 706; do
  tail -n 1 "research/deep_n100_seed${seed}.log"
done
exit "$status"
