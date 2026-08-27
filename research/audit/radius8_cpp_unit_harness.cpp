#define main radius8_production_main
#include "../radius8_cpp_antichain_dfs.cpp"
#undef main

#include <iostream>
#include <random>

static Mask random_mask(std::mt19937_64& rng, int maximum_size) {
  Mask result{};
  const int wanted = static_cast<int>(rng() % (maximum_size + 1));
  while (population(result) < wanted) {
    const int bit = static_cast<int>(rng() % 164);
    result.w[bit >> 6] |= std::uint64_t{1} << (bit & 63);
  }
  return result;
}

static std::vector<Mask> brute_minimize(std::vector<Mask> values) {
  std::sort(values.begin(), values.end(), mask_size_less);
  values.erase(std::unique(values.begin(), values.end()), values.end());
  std::vector<Mask> kept;
  for (const auto& value : values) {
    bool dominated = false;
    for (const auto& old : kept)
      if (subset_of(old, value)) dominated = true;
    if (!dominated) kept.push_back(value);
  }
  return kept;
}

static bool same_masks(std::vector<Mask> left, std::vector<Mask> right) {
  std::sort(left.begin(), left.end(), mask_less);
  std::sort(right.begin(), right.end(), mask_less);
  return left == right;
}

static int brute_clique(const std::vector<Bits>& adjacency, int n) {
  int best = 0;
  const unsigned limit = 1U << n;
  for (unsigned subset = 0; subset < limit; ++subset) {
    const int size = __builtin_popcount(subset);
    if (size <= best) continue;
    bool clique = true;
    for (int a = 0; a < n && clique; ++a)
      if ((subset >> a) & 1U)
        for (int b = a + 1; b < n; ++b)
          if ((subset >> b) & 1U)
            if (!test_bit(adjacency[a], b)) {
              clique = false;
              break;
            }
    if (clique) best = size;
  }
  return best;
}

int main() {
  std::mt19937_64 rng(0x20260827ULL);
  for (int trial = 0; trial < 5000; ++trial) {
    const int radius = 1 + static_cast<int>(rng() % 8);
    std::vector<Mask> family, covers;
    for (int i = 0, count = 1 + static_cast<int>(rng() % 12); i < count; ++i)
      family.push_back(random_mask(rng, radius));
    for (int i = 0, count = 1 + static_cast<int>(rng() % 12); i < count; ++i)
      covers.push_back(random_mask(rng, radius));
    family = brute_minimize(std::move(family));
    covers = brute_minimize(std::move(covers));
    const Mask forced = random_mask(rng, radius + 2);

    std::vector<Mask> expected;
    for (const auto& old : family)
      for (const auto& cover : covers) {
        const auto combined = united(united(old, forced), cover);
        if (population(combined) <= radius) expected.push_back(combined);
      }
    expected = brute_minimize(std::move(expected));
    Instance instance;
    instance.radius = radius;
    Search search(std::move(instance), {}, 1, 1000.0);
    const auto actual = search.extend_family(family, covers, forced);
    if (!same_masks(expected, actual)) {
      std::cerr << "antichain mismatch at trial " << trial << '\n';
      return 1;
    }
  }

  for (int n = 1; n <= 14; ++n) {
    for (int trial = 0; trial < 100; ++trial) {
      const int words = (n + 63) / 64;
      std::vector<Bits> graph(n, Bits(words));
      for (int a = 0; a < n; ++a)
        for (int b = a + 1; b < n; ++b)
          if ((rng() & 3U) != 0) {
            set_bit(graph[a], b);
            set_bit(graph[b], a);
          }
      Instance instance;
      Search search(std::move(instance), {}, 1, 1000.0);
      search.words = words;
      search.adjacency = graph;
      Bits possible(words, ~std::uint64_t{0});
      if (n & 63) possible.back() &= (std::uint64_t{1} << (n & 63)) - 1;
      const int bound = search.greedy_color_upper_bound(possible, n);
      const int exact = brute_clique(graph, n);
      if (bound < exact) {
        std::cerr << "invalid coloring bound n=" << n << " trial=" << trial
                  << " bound=" << bound << " clique=" << exact << '\n';
        return 2;
      }
      auto order = degeneracy_order(graph);
      std::sort(order.begin(), order.end());
      for (int i = 0; i < n; ++i)
        if (order[i] != i) return 3;
    }
  }
  std::cout << "status=VERIFIED antichain_trials=5000 "
               "coloring_graphs=1400 max_vertices=14\n";
  return 0;
}
