#!/usr/bin/env bash
set -euo pipefail

solver="research/no_isosceles_deep_r6"
notebook="alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
seconds="${1:-180}"

pids=()
for seed in 801 802 803 804 805 806; do
  "$solver" --n 100 --seconds "$seconds" --seed "$seed" --deep 1 --deep-radius 6 \
    --notebook "$notebook" --out "research/deep_r6_n100_seed${seed}.txt" \
    >"research/deep_r6_n100_seed${seed}.log" 2>&1 &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

for seed in 801 802 803 804 805 806; do
  tail -n 1 "research/deep_r6_n100_seed${seed}.log"
done
exit "$status"
