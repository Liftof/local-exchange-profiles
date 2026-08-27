// Exact C++ port of radius7_exchange_dfs.py for the compact RPC1 input.
//
// The search state is an antichain of inclusion-minimal masks of record
// vertices whose deletion supports every selected outsider.  Pair
// compatibility is only a necessary graph filter; common-mask feasibility and
// all-outsider isosceles triples are checked exactly at every extension.

// Build:
//   g++ -O3 -DNDEBUG -std=c++20 radius8_cpp_antichain_dfs.cpp -o solver
// Run:
//   solver INPUT.bin PAIRS.json TARGET SECONDS OUTPUT.json

// No proof trace is emitted.  SAT witnesses must additionally be checked by
// radius8_cpp_verify.py, which performs a direct cubic integer-geometry test.

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

struct Mask {
  std::array<std::uint64_t, 3> w{};
  bool operator==(const Mask&) const = default;
};

static inline Mask united(const Mask& a, const Mask& b) {
  return {{{a.w[0] | b.w[0], a.w[1] | b.w[1], a.w[2] | b.w[2]}}};
}

static inline int population(const Mask& a) {
  return __builtin_popcountll(a.w[0]) + __builtin_popcountll(a.w[1]) +
         __builtin_popcountll(a.w[2]);
}

// Numeric ordering of the 192-bit integer, matching Python's integer order.
static inline bool mask_less(const Mask& a, const Mask& b) {
  if (a.w[2] != b.w[2]) return a.w[2] < b.w[2];
  if (a.w[1] != b.w[1]) return a.w[1] < b.w[1];
  return a.w[0] < b.w[0];
}

static inline bool mask_size_less(const Mask& a, const Mask& b) {
  const int pa = population(a), pb = population(b);
  return pa != pb ? pa < pb : mask_less(a, b);
}

static inline bool subset_of(const Mask& a, const Mask& b) {
  return ((a.w[0] & ~b.w[0]) | (a.w[1] & ~b.w[1]) |
          (a.w[2] & ~b.w[2])) == 0;
}

template <class T>
static void read_exact(std::ifstream& in, T& value) {
  in.read(reinterpret_cast<char*>(&value), sizeof(value));
  if (!in) throw std::runtime_error("truncated binary input");
}

struct Point {
  std::uint16_t x{}, y{};
  bool operator==(const Point&) const = default;
};

struct Candidate {
  Point point;
  std::vector<Mask> covers;
  std::uint32_t old_index{};
};

using Bits = std::vector<std::uint64_t>;

static inline void set_bit(Bits& bits, int vertex) {
  bits[vertex >> 6] |= std::uint64_t{1} << (vertex & 63);
}

static inline void clear_bit(Bits& bits, int vertex) {
  bits[vertex >> 6] &= ~(std::uint64_t{1} << (vertex & 63));
}

static inline bool test_bit(const Bits& bits, int vertex) {
  return (bits[vertex >> 6] >> (vertex & 63)) & 1U;
}

static inline int bits_population(const Bits& bits) {
  int total = 0;
  for (const auto word : bits) total += __builtin_popcountll(word);
  return total;
}

static inline int pop_first(Bits& bits) {
  for (std::size_t word = 0; word < bits.size(); ++word) {
    if (bits[word]) {
      const int offset = __builtin_ctzll(bits[word]);
      bits[word] &= bits[word] - 1;
      return static_cast<int>(word * 64 + offset);
    }
  }
  return -1;
}

static std::string read_text(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open JSON input: " + path);
  std::ostringstream buffer;
  buffer << in.rdbuf();
  return buffer.str();
}

static std::size_t after_key(const std::string& text, const std::string& key) {
  const std::string needle = "\"" + key + "\":";
  const auto found = text.find(needle);
  if (found == std::string::npos) throw std::runtime_error("missing JSON key: " + key);
  return found + needle.size();
}

static std::uint64_t parse_uint_at(const std::string& text, std::size_t& pos) {
  while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
  if (pos == text.size() || !std::isdigit(static_cast<unsigned char>(text[pos])))
    throw std::runtime_error("expected unsigned JSON integer");
  std::uint64_t value = 0;
  while (pos < text.size() && std::isdigit(static_cast<unsigned char>(text[pos]))) {
    value = value * 10 + static_cast<unsigned>(text[pos++] - '0');
  }
  return value;
}

static std::uint64_t json_uint(const std::string& text, const std::string& key) {
  auto pos = after_key(text, key);
  return parse_uint_at(text, pos);
}

static std::string json_string(const std::string& text, const std::string& key) {
  auto pos = after_key(text, key);
  while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
  if (pos == text.size() || text[pos++] != '"') throw std::runtime_error("expected JSON string");
  const auto end = text.find('"', pos);
  if (end == std::string::npos) throw std::runtime_error("unterminated JSON string");
  return text.substr(pos, end - pos);
}

static std::vector<std::pair<std::uint32_t, std::uint32_t>> json_pair_array(
    const std::string& text, const std::string& key) {
  auto pos = after_key(text, key);
  while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
  if (pos == text.size() || text[pos++] != '[') throw std::runtime_error("expected JSON array");
  std::vector<std::pair<std::uint32_t, std::uint32_t>> result;
  while (true) {
    while (pos < text.size() &&
           (std::isspace(static_cast<unsigned char>(text[pos])) || text[pos] == ','))
      ++pos;
    if (pos == text.size()) throw std::runtime_error("unterminated pair array");
    if (text[pos] == ']') {
      ++pos;
      break;
    }
    if (text[pos++] != '[') throw std::runtime_error("expected pair opening bracket");
    const auto a = parse_uint_at(text, pos);
    while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
    if (pos == text.size() || text[pos++] != ',') throw std::runtime_error("expected pair comma");
    const auto b = parse_uint_at(text, pos);
    while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
    if (pos == text.size() || text[pos++] != ']') throw std::runtime_error("expected pair closing bracket");
    if (a > std::numeric_limits<std::uint32_t>::max() ||
        b > std::numeric_limits<std::uint32_t>::max())
      throw std::runtime_error("pair value out of range");
    result.emplace_back(static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(b));
  }
  return result;
}

static inline std::int64_t squared_distance(const Point& a, const Point& b) {
  const std::int64_t dx = static_cast<int>(a.x) - static_cast<int>(b.x);
  const std::int64_t dy = static_cast<int>(a.y) - static_cast<int>(b.y);
  return dx * dx + dy * dy;
}

static inline bool is_isosceles(const Point& a, const Point& b, const Point& c) {
  const auto ab = squared_distance(a, b);
  const auto ac = squared_distance(a, c);
  const auto bc = squared_distance(b, c);
  return ab == ac || ab == bc || ac == bc;
}

struct Instance {
  std::uint32_t grid_n{}, radius{}, record_size{}, candidate_count{};
  std::string digest;
  std::vector<Candidate> candidates;
  std::unordered_map<std::uint64_t, Mask> forced;
  std::uint64_t total_covers{};
};

static Instance read_rpc1(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) throw std::runtime_error("cannot open binary input: " + path);
  char magic[4];
  in.read(magic, 4);
  if (std::string(magic, 4) != "RPC1") throw std::runtime_error("bad RPC1 magic");
  Instance instance;
  read_exact(in, instance.grid_n);
  read_exact(in, instance.radius);
  read_exact(in, instance.record_size);
  read_exact(in, instance.candidate_count);
  char digest_chars[64];
  in.read(digest_chars, 64);
  if (!in) throw std::runtime_error("truncated RPC1 digest");
  instance.digest.assign(digest_chars, 64);
  instance.candidates.resize(instance.candidate_count);
  for (std::uint32_t index = 0; index < instance.candidate_count; ++index) {
    auto& candidate = instance.candidates[index];
    read_exact(in, candidate.point.x);
    read_exact(in, candidate.point.y);
    candidate.old_index = index;
    std::uint32_t count;
    read_exact(in, count);
    candidate.covers.resize(count);
    for (auto& mask : candidate.covers) {
      read_exact(in, mask.w[0]);
      read_exact(in, mask.w[1]);
      read_exact(in, mask.w[2]);
      if (population(mask) > static_cast<int>(instance.radius))
        throw std::runtime_error("cover exceeds radius");
    }
    std::sort(candidate.covers.begin(), candidate.covers.end(), mask_size_less);
    candidate.covers.erase(std::unique(candidate.covers.begin(), candidate.covers.end()),
                           candidate.covers.end());
    instance.total_covers += candidate.covers.size();
  }
  std::uint32_t required_count;
  read_exact(in, required_count);
  instance.forced.reserve(required_count * 2);
  for (std::uint32_t i = 0; i < required_count; ++i) {
    std::uint32_t left, right;
    Mask mask;
    read_exact(in, left);
    read_exact(in, right);
    read_exact(in, mask.w[0]);
    read_exact(in, mask.w[1]);
    read_exact(in, mask.w[2]);
    if (left >= right || right >= instance.candidate_count)
      throw std::runtime_error("invalid forced-pair indices");
    instance.forced.emplace(static_cast<std::uint64_t>(left) * instance.candidate_count + right,
                            mask);
  }
  char trailing;
  if (in.read(&trailing, 1)) throw std::runtime_error("trailing RPC1 data");
  return instance;
}

static std::vector<int> degeneracy_order(const std::vector<Bits>& adjacency) {
  const int n = static_cast<int>(adjacency.size());
  std::vector<int> degree(n), removed_order;
  std::vector<unsigned char> removed(n, 0);
  using Entry = std::pair<int, int>;
  std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
  for (int vertex = 0; vertex < n; ++vertex) {
    degree[vertex] = bits_population(adjacency[vertex]);
    queue.emplace(degree[vertex], vertex);
  }
  removed_order.reserve(n);
  while (static_cast<int>(removed_order.size()) < n) {
    auto [stored_degree, vertex] = queue.top();
    queue.pop();
    if (removed[vertex] || stored_degree != degree[vertex]) continue;
    removed[vertex] = 1;
    removed_order.push_back(vertex);
    for (std::size_t word = 0; word < adjacency[vertex].size(); ++word) {
      auto neighbors = adjacency[vertex][word];
      while (neighbors) {
        const int bit = __builtin_ctzll(neighbors);
        neighbors &= neighbors - 1;
        const int other = static_cast<int>(word * 64 + bit);
        if (other < n && !removed[other]) {
          --degree[other];
          queue.emplace(degree[other], other);
        }
      }
    }
  }
  std::reverse(removed_order.begin(), removed_order.end());
  return removed_order;
}

struct Search {
  Instance instance;
  std::vector<Bits> adjacency;
  std::vector<std::pair<int, int>> edges;
  std::vector<int> edge_id;  // dense symmetric lookup, -1 for non-edge
  std::vector<Bits> triple_block;
  std::vector<int> order;
  std::vector<int> old_to_new;
  int words{}, target{};
  std::chrono::steady_clock::time_point started, deadline;
  bool timed_out = false;
  std::uint64_t nodes = 0, family_extensions = 0, cover_union_tests = 0;
  std::uint64_t masks_generated = 0, pruned_cardinality = 0, pruned_coloring = 0;
  std::uint64_t pruned_removals = 0, pruned_outside_triples = 0;
  std::size_t max_family_size = 0;
  std::vector<int> witness_selected;
  std::vector<Mask> witness_family;

  Search(Instance input, const std::vector<std::pair<std::uint32_t, std::uint32_t>>& old_pairs,
         int requested_target, double seconds)
      : instance(std::move(input)), target(requested_target) {
    started = std::chrono::steady_clock::now();
    deadline = started + std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                             std::chrono::duration<double>(seconds));
    const int n = static_cast<int>(instance.candidate_count);
    words = (n + 63) / 64;
    std::vector<Bits> old_adjacency(n, Bits(words));
    for (const auto [left, right] : old_pairs) {
      if (left >= instance.candidate_count || right >= instance.candidate_count || left >= right)
        throw std::runtime_error("invalid compatible pair");
      if (test_bit(old_adjacency[left], right)) throw std::runtime_error("duplicate pair");
      set_bit(old_adjacency[left], right);
      set_bit(old_adjacency[right], left);
    }

    order = degeneracy_order(old_adjacency);
    old_to_new.resize(n);
    for (int new_index = 0; new_index < n; ++new_index) old_to_new[order[new_index]] = new_index;

    std::vector<Candidate> relabeled;
    relabeled.reserve(n);
    for (const int old : order) relabeled.push_back(std::move(instance.candidates[old]));
    instance.candidates = std::move(relabeled);

    adjacency.assign(n, Bits(words));
    edges.reserve(old_pairs.size());
    for (const auto [old_left, old_right] : old_pairs) {
      int left = old_to_new[old_left], right = old_to_new[old_right];
      set_bit(adjacency[left], right);
      set_bit(adjacency[right], left);
      if (left > right) std::swap(left, right);
      edges.emplace_back(left, right);
    }
    std::sort(edges.begin(), edges.end());

    // Precompute the set of third candidates that forms an all-outsider
    // isosceles triple for every compatible pair.  This is exactly equivalent
    // to the Python geometry loops and makes filtering a few word operations.
    edge_id.assign(static_cast<std::size_t>(n) * n, -1);
    triple_block.assign(edges.size(), Bits(words));
    for (std::size_t id = 0; id < edges.size(); ++id) {
      const auto [left, right] = edges[id];
      edge_id[static_cast<std::size_t>(left) * n + right] = static_cast<int>(id);
      edge_id[static_cast<std::size_t>(right) * n + left] = static_cast<int>(id);
      for (int third = 0; third < n; ++third) {
        if (third != left && third != right &&
            is_isosceles(instance.candidates[left].point, instance.candidates[right].point,
                         instance.candidates[third].point))
          set_bit(triple_block[id], third);
      }
    }
  }

  inline const Mask* forced_mask(int rel_left, int rel_right) const {
    auto old_left = instance.candidates[rel_left].old_index;
    auto old_right = instance.candidates[rel_right].old_index;
    if (old_left > old_right) std::swap(old_left, old_right);
    const auto found = instance.forced.find(static_cast<std::uint64_t>(old_left) *
                                                instance.candidate_count +
                                            old_right);
    return found == instance.forced.end() ? nullptr : &found->second;
  }

  inline const Bits& blocked_thirds(int left, int right) const {
    const int id = edge_id[static_cast<std::size_t>(left) * instance.candidate_count + right];
    if (id < 0) throw std::runtime_error("triple lookup on non-edge");
    return triple_block[id];
  }

  bool deadline_reached() {
    if (std::chrono::steady_clock::now() >= deadline) {
      timed_out = true;
      return true;
    }
    return false;
  }

  std::vector<Mask> extend_family(const std::vector<Mask>& family,
                                  const std::vector<Mask>& covers, const Mask& forced) {
    std::vector<Mask> values;
    values.reserve(family.size());
    bool every_partial_full = true;
    for (const auto& old : family) {
      const Mask partial = united(old, forced);
      const int partial_size = population(partial);
      if (partial_size > static_cast<int>(instance.radius)) continue;
      if (partial_size == static_cast<int>(instance.radius)) {
        // At full radius a union can survive only if a cover is already a
        // subset.  In that dominant case the old mask remains unchanged.
        for (const auto& cover : covers) {
          ++cover_union_tests;
          if (subset_of(cover, partial)) {
            values.push_back(partial);
            break;
          }
        }
      } else {
        every_partial_full = false;
        for (const auto& cover : covers) {
          ++cover_union_tests;
          const Mask combined = united(partial, cover);
          if (population(combined) <= static_cast<int>(instance.radius))
            values.push_back(combined);
        }
      }
    }
    if (values.empty()) return {};

    // If every contributing partial mask was already full, all output masks
    // have equal cardinality.  Sorting/uniquing is sufficient; no strict
    // subset can exist.  The general branch performs the exact antichain
    // minimization used by the Python reference.
    std::sort(values.begin(), values.end(), every_partial_full ? mask_less : mask_size_less);
    values.erase(std::unique(values.begin(), values.end()), values.end());
    if (every_partial_full) return values;

    std::vector<Mask> kept;
    kept.reserve(values.size());
    for (const auto& mask : values) {
      bool dominated = false;
      for (const auto& old : kept) {
        if (subset_of(old, mask)) {
          dominated = true;
          break;
        }
      }
      if (!dominated) kept.push_back(mask);
    }
    return kept;
  }

  // A quick exact clique upper bound: greedily partition possible vertices
  // into independent sets.  The number of color classes upper-bounds any
  // clique and can only prune impossible branches.
  int greedy_color_upper_bound(const Bits& possible, int stop_at) const {
#ifdef R8CPP_NO_COLOR_PRUNING
    (void)possible;
    return stop_at;
#else
    Bits uncolored = possible;
    int colors = 0;
    while (bits_population(uncolored) && colors < stop_at) {
      ++colors;
      Bits available = uncolored;
      while (true) {
        const int vertex = pop_first(available);
        if (vertex < 0) break;
        clear_bit(uncolored, vertex);
        for (int word = 0; word < words; ++word) available[word] &= ~adjacency[vertex][word];
      }
    }
    return colors;
#endif
  }

  bool dfs(std::vector<int>& selected, const std::vector<Mask>& family, const Bits& possible) {
    ++nodes;
    if ((nodes & 2047U) == 0 && deadline_reached()) return false;
    if (static_cast<int>(selected.size()) >= target) {
      witness_selected = selected;
      witness_family = family;
      return true;
    }
    const int need = target - static_cast<int>(selected.size());
    if (bits_population(possible) < need) {
      ++pruned_cardinality;
      return false;
    }
    if (greedy_color_upper_bound(possible, need) < need) {
      ++pruned_coloring;
      return false;
    }

    Bits remaining = possible;
    while (true) {
      if ((family_extensions & 16383U) == 0 && deadline_reached()) return false;
      const int vertex = pop_first(remaining);
      if (vertex < 0) break;
      if (1 + bits_population(remaining) < need) {
        ++pruned_cardinality;
        return false;
      }

      bool triple_bad = false;
#ifndef R8CPP_RELAX_OUTSIDE_TRIPLES
      for (std::size_t i = 0; i < selected.size() && !triple_bad; ++i) {
        for (std::size_t j = i + 1; j < selected.size(); ++j) {
          if (test_bit(blocked_thirds(selected[i], selected[j]), vertex)) {
            triple_bad = true;
            break;
          }
        }
      }
#endif
      if (triple_bad) {
        ++pruned_outside_triples;
        continue;
      }

      Mask forced{};
      for (const int old : selected) {
        if (const auto* pair_mask = forced_mask(old, vertex)) forced = united(forced, *pair_mask);
      }
      auto next_family = extend_family(family, instance.candidates[vertex].covers, forced);
      ++family_extensions;
      masks_generated += next_family.size();
      max_family_size = std::max(max_family_size, next_family.size());
      if (next_family.empty()) {
        ++pruned_removals;
        continue;
      }

      Bits filtered(words);
      for (int word = 0; word < words; ++word)
        filtered[word] = remaining[word] & adjacency[vertex][word];
      for (const int old : selected) {
#ifndef R8CPP_RELAX_OUTSIDE_TRIPLES
        const auto& blocked = blocked_thirds(old, vertex);
        for (int word = 0; word < words; ++word) filtered[word] &= ~blocked[word];
#else
        (void)old;
#endif
      }
      if (static_cast<int>(selected.size()) + 1 + bits_population(filtered) < target) {
        ++pruned_cardinality;
        continue;
      }
      if (greedy_color_upper_bound(filtered, target - static_cast<int>(selected.size()) - 1) <
          target - static_cast<int>(selected.size()) - 1) {
        ++pruned_coloring;
        continue;
      }
      selected.push_back(vertex);
      if (dfs(selected, next_family, filtered)) return true;
      selected.pop_back();
      if (timed_out) return false;
    }
    return false;
  }

  bool solve() {
    Bits possible(words, ~std::uint64_t{0});
    if (instance.candidate_count & 63)
      possible.back() &= (std::uint64_t{1} << (instance.candidate_count & 63)) - 1;
    std::vector<int> selected;
    const std::vector<Mask> initial(1);
    return dfs(selected, initial, possible);
  }
};

static void write_mask_indices(std::ostream& out, const Mask& mask, int record_size) {
  out << '[';
  bool first = true;
  for (int index = 0; index < record_size; ++index) {
    if ((mask.w[index >> 6] >> (index & 63)) & 1U) {
      if (!first) out << ',';
      first = false;
      out << index;
    }
  }
  out << ']';
}

int main(int argc, char** argv) try {
  if (argc != 6) {
    std::cerr << "usage: radius8_cpp_antichain_dfs INPUT.bin PAIRS.json TARGET SECONDS OUTPUT.json\n";
    return 2;
  }
  const auto global_started = std::chrono::steady_clock::now();
  const int target = std::stoi(argv[3]);
  const double seconds = std::stod(argv[4]);
  if (target <= 0 || seconds <= 0) throw std::runtime_error("target and seconds must be positive");
  auto instance = read_rpc1(argv[1]);
  const std::string cache = read_text(argv[2]);
  if (json_uint(cache, "n") != instance.grid_n ||
      json_uint(cache, "radius") != instance.radius ||
      json_uint(cache, "record_size") != instance.record_size ||
      json_uint(cache, "eligible_candidate_count") != instance.candidate_count ||
      json_string(cache, "record_sha256") != instance.digest)
    throw std::runtime_error("binary/JSON metadata mismatch");
  const auto cached_candidates = json_pair_array(cache, "eligible_candidates");
  if (cached_candidates.size() != instance.candidates.size())
    throw std::runtime_error("candidate list length mismatch");
  for (std::size_t i = 0; i < cached_candidates.size(); ++i) {
    if (cached_candidates[i].first != instance.candidates[i].point.x ||
        cached_candidates[i].second != instance.candidates[i].point.y)
      throw std::runtime_error("candidate coordinate mismatch");
  }
  const auto pairs = json_pair_array(cache, "compatible_pairs");
  if (pairs.size() != json_uint(cache, "compatible_pair_count"))
    throw std::runtime_error("compatible pair count mismatch");

  // Construction time is included in the user-visible total bound.  Give the
  // DFS the remaining budget after parsing and preprocessing.
  const double setup_before_search =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - global_started).count();
  const double search_budget = std::max(0.001, seconds - setup_before_search);
  Search search(std::move(instance), pairs, target, search_budget);
  const bool found = search.solve();
  const double elapsed =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - global_started).count();
  const std::string status = found ? "SAT" : search.timed_out ? "UNKNOWN" : "UNSAT";

  std::ofstream out(argv[5]);
  if (!out) throw std::runtime_error("cannot open output");
  out << "{\n"
      << "  \"format\": \"radius8-cpp-antichain-dfs-v1\",\n"
#ifdef R8CPP_RELAX_OUTSIDE_TRIPLES
      << "  \"outside_triple_constraints\": false,\n"
      << "  \"exact_model\": false,\n"
      << "  \"model_note\": \"necessary-condition relaxation without all-outsider triples\",\n"
#else
      << "  \"outside_triple_constraints\": true,\n"
      << "  \"exact_model\": true,\n"
#endif
#ifdef R8CPP_NO_COLOR_PRUNING
      << "  \"color_pruning\": false,\n"
#else
      << "  \"color_pruning\": true,\n"
#endif
      << "  \"status\": \"" << status << "\",\n"
      << "  \"n\": " << search.instance.grid_n << ",\n"
      << "  \"record_size\": " << search.instance.record_size << ",\n"
      << "  \"radius_removed\": " << search.instance.radius << ",\n"
      << "  \"target_added\": " << target << ",\n"
      << "  \"eligible_candidates\": " << search.instance.candidate_count << ",\n"
      << "  \"minimal_covers\": " << search.instance.total_covers << ",\n"
      << "  \"forced_pair_entries\": " << search.instance.forced.size() << ",\n"
      << "  \"compatible_pairs\": " << pairs.size() << ",\n"
      << "  \"nodes\": " << search.nodes << ",\n"
      << "  \"family_extensions\": " << search.family_extensions << ",\n"
      << "  \"cover_union_tests\": " << search.cover_union_tests << ",\n"
      << "  \"masks_generated\": " << search.masks_generated << ",\n"
      << "  \"max_family_size\": " << search.max_family_size << ",\n"
      << "  \"pruned_cardinality\": " << search.pruned_cardinality << ",\n"
      << "  \"pruned_coloring\": " << search.pruned_coloring << ",\n"
      << "  \"pruned_removals\": " << search.pruned_removals << ",\n"
      << "  \"pruned_outside_triples\": " << search.pruned_outside_triples << ",\n"
      << "  \"elapsed_seconds\": " << elapsed << ",\n"
      << "  \"input_record_sha256\": \"" << search.instance.digest << "\"";
  if (found) {
    Mask removal = search.witness_family.front();
    for (int vertex = 0;
         vertex < static_cast<int>(search.instance.record_size) &&
         population(removal) < static_cast<int>(search.instance.radius);
         ++vertex)
      removal.w[vertex >> 6] |= std::uint64_t{1} << (vertex & 63);
    out << ",\n  \"removal_indices\": ";
    write_mask_indices(out, removal, search.instance.record_size);
    out << ",\n  \"addition_old_indices\": [";
    for (std::size_t i = 0; i < search.witness_selected.size(); ++i) {
      if (i) out << ',';
      out << search.instance.candidates[search.witness_selected[i]].old_index;
    }
    out << "],\n  \"additions\": [";
    for (std::size_t i = 0; i < search.witness_selected.size(); ++i) {
      if (i) out << ',';
      const auto point = search.instance.candidates[search.witness_selected[i]].point;
      out << '[' << point.x << ',' << point.y << ']';
    }
    out << ']';
  }
  out << "\n}\n";
  std::cout << "status=" << status << " radius=" << search.instance.radius
            << " target=" << target << " nodes=" << search.nodes
            << " extensions=" << search.family_extensions << " seconds=" << elapsed
            << " output=" << argv[5] << "\n";
  return found ? 10 : status == "UNSAT" ? 20 : 0;
} catch (const std::exception& error) {
  std::cerr << "error: " << error.what() << '\n';
  return 1;
}
