#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <numeric>
#include <random>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using Clock = std::chrono::steady_clock;

struct Config {
  int n = 64;
  int seed_n = 0;
  bool symmetric = false;
  bool analyze = false;
  bool analyze3 = false;
  bool analyze4 = false;
  bool analyze5 = false;
  bool deep = false;
  int deep_radius = 0;
  int seconds = 60;
  uint64_t seed = 1;
  std::string notebook;
  std::string output = "best_points.txt";
};

static Config parse_args(int argc, char** argv) {
  Config cfg;
  for (int i = 1; i + 1 < argc; i += 2) {
    const std::string key = argv[i];
    const std::string value = argv[i + 1];
    if (key == "--n") cfg.n = std::stoi(value);
    else if (key == "--seed-n") cfg.seed_n = std::stoi(value);
    else if (key == "--symmetric") cfg.symmetric = std::stoi(value) != 0;
    else if (key == "--analyze") cfg.analyze = std::stoi(value) != 0;
    else if (key == "--analyze3") cfg.analyze3 = std::stoi(value) != 0;
    else if (key == "--analyze4") cfg.analyze4 = std::stoi(value) != 0;
    else if (key == "--analyze5") cfg.analyze5 = std::stoi(value) != 0;
    else if (key == "--deep") cfg.deep = std::stoi(value) != 0;
    else if (key == "--deep-radius") cfg.deep_radius = std::stoi(value);
    else if (key == "--seconds") cfg.seconds = std::stoi(value);
    else if (key == "--seed") cfg.seed = std::stoull(value);
    else if (key == "--notebook") cfg.notebook = value;
    else if (key == "--out") cfg.output = value;
    else throw std::runtime_error("Unknown argument: " + key);
  }
  if (cfg.notebook.empty()) throw std::runtime_error("--notebook is required");
  return cfg;
}

static std::vector<int> load_seed(const Config& cfg) {
  std::ifstream in(cfg.notebook);
  if (!in) throw std::runtime_error("Cannot open notebook: " + cfg.notebook);
  std::ostringstream buffer;
  buffer << in.rdbuf();
  const std::string text = buffer.str();
  const int source_n = cfg.seed_n > 0 ? cfg.seed_n : cfg.n;
  const std::string marker = "sol_" + std::to_string(source_n) + " = [";
  const size_t start = text.find(marker);
  if (start == std::string::npos) throw std::runtime_error("Seed marker not found: " + marker);
  const size_t end = text.find(']', start + marker.size());
  if (end == std::string::npos) throw std::runtime_error("Seed list is not closed");
  const std::string body = text.substr(start, end - start + 1);
  const std::regex pair_re(R"(\((-?\d+),\s*(-?\d+)\))");
  std::vector<int> points;
  for (auto it = std::sregex_iterator(body.begin(), body.end(), pair_re);
       it != std::sregex_iterator(); ++it) {
    const int x = std::stoi((*it)[1].str());
    const int y = std::stoi((*it)[2].str());
    if (x < 0 || x >= cfg.n || y < 0 || y >= cfg.n) {
      throw std::runtime_error("Out-of-range point in seed");
    }
    points.push_back(x * cfg.n + y);
  }
  if (points.empty()) throw std::runtime_error("Parsed an empty seed");
  return points;
}

class IsoscelesFreeSet {
 public:
  explicit IsoscelesFreeSet(int n)
      : n_(n), total_(n * n), selected_(total_, false), distances_(total_),
        seen_(2 * (n - 1) * (n - 1) + 1, 0) {}

  int size() const { return static_cast<int>(points_.size()); }
  const std::vector<int>& points() const { return points_; }
  bool contains(int p) const { return selected_[p]; }

  int dist2(int a, int b) const {
    const int ax = a / n_, ay = a % n_;
    const int bx = b / n_, by = b % n_;
    const int dx = ax - bx, dy = ay - by;
    return dx * dx + dy * dy;
  }

  bool check_add(int p) {
    if (selected_[p]) return false;
    ++stamp_;
    if (stamp_ == 0) {
      std::fill(seen_.begin(), seen_.end(), 0);
      stamp_ = 1;
    }
    for (int q : points_) {
      const int d = dist2(p, q);
      if (seen_[d] == stamp_) return false;        // p would be the apex.
      seen_[d] = stamp_;
      if (distances_[q].count(d)) return false;    // q would be the apex.
    }
    return true;
  }

  bool add(int p) {
    if (!check_add(p)) return false;
    add_unchecked(p);
    return true;
  }

  void add_unchecked(int p) {
    distances_[p].clear();
    distances_[p].reserve(points_.size() * 2 + 1);
    for (int q : points_) {
      const int d = dist2(p, q);
      distances_[q].insert(d);
      distances_[p].insert(d);
    }
    selected_[p] = true;
    points_.push_back(p);
  }

  void remove(int p) {
    if (!selected_[p]) return;
    selected_[p] = false;
    auto it = std::find(points_.begin(), points_.end(), p);
    points_.erase(it);
    for (int q : points_) distances_[q].erase(dist2(p, q));
    distances_[p].clear();
  }

  void reset(const std::vector<int>& seed) {
    for (int p : points_) distances_[p].clear();
    std::fill(selected_.begin(), selected_.end(), false);
    points_.clear();
    points_.reserve(seed.size() + 32);
    for (int p : seed) add_unchecked(p);
  }

  bool verify() const {
    for (int apex : points_) {
      std::unordered_set<int> used;
      used.reserve(points_.size() * 2);
      for (int q : points_) {
        if (q == apex) continue;
        if (!used.insert(dist2(apex, q)).second) return false;
      }
    }
    return true;
  }

 private:
  int n_;
  int total_;
  std::vector<uint8_t> selected_;
  std::vector<int> points_;
  std::vector<std::unordered_set<int>> distances_;
  std::vector<uint32_t> seen_;
  uint32_t stamp_ = 0;
};

static void write_solution(const std::string& path, int n, const std::vector<int>& points,
                           uint64_t seed, long long iteration) {
  std::vector<int> ordered = points;
  std::sort(ordered.begin(), ordered.end());
  std::ofstream out(path, std::ios::trunc);
  out << "n=" << n << "\nsize=" << ordered.size() << "\nseed=" << seed
      << "\niteration=" << iteration << "\npoints=[";
  for (size_t i = 0; i < ordered.size(); ++i) {
    if (i) out << ',';
    out << '(' << ordered[i] / n << ',' << ordered[i] % n << ')';
  }
  out << "]\n";
}

static int border_distance(int p, int n) {
  const int x = p / n, y = p % n;
  return std::min(std::min(x, n - 1 - x), std::min(y, n - 1 - y));
}

using Edge = std::pair<int, int>;

static std::vector<Edge> conflict_edges(const IsoscelesFreeSet& state, int p) {
  const auto& points = state.points();
  std::vector<Edge> edges;
  for (size_t i = 0; i < points.size(); ++i) {
    const int a = points[i];
    const int dpa = state.dist2(p, a);
    for (size_t j = i + 1; j < points.size(); ++j) {
      const int b = points[j];
      const int dpb = state.dist2(p, b);
      const int dab = state.dist2(a, b);
      if (dpa == dpb || dpa == dab || dpb == dab) edges.emplace_back(a, b);
    }
  }
  return edges;
}

static int matching_lower_bound(const std::vector<Edge>& edges, int total) {
  std::vector<uint8_t> used(total, false);
  int matching = 0;
  for (const auto& [a, b] : edges) {
    if (!used[a] && !used[b]) {
      used[a] = used[b] = true;
      ++matching;
    }
  }
  return matching;
}

static bool vertex_cover_bounded(const std::vector<Edge>& edges, int budget, int total,
                                 std::vector<int>& cover) {
  if (edges.empty()) return true;
  if (budget == 0 || matching_lower_bound(edges, total) > budget) return false;

  std::vector<int> degree(total, 0);
  for (const auto& [a, b] : edges) {
    ++degree[a];
    ++degree[b];
  }
  Edge pivot = edges.front();
  int pivot_score = -1;
  for (const auto& edge : edges) {
    const int score = degree[edge.first] + degree[edge.second];
    if (score > pivot_score) {
      pivot = edge;
      pivot_score = score;
    }
  }

  for (int chosen : {pivot.first, pivot.second}) {
    std::vector<Edge> remaining;
    remaining.reserve(edges.size() - degree[chosen]);
    for (const auto& edge : edges) {
      if (edge.first != chosen && edge.second != chosen) remaining.push_back(edge);
    }
    cover.push_back(chosen);
    if (vertex_cover_bounded(remaining, budget - 1, total, cover)) return true;
    cover.pop_back();
  }
  return false;
}

static std::vector<int> minimum_vertex_cover_up_to(const std::vector<Edge>& edges,
                                                    int max_budget, int total) {
  const int lower = matching_lower_bound(edges, total);
  for (int budget = lower; budget <= max_budget; ++budget) {
    std::vector<int> cover;
    cover.reserve(budget);
    if (vertex_cover_bounded(edges, budget, total, cover)) return cover;
  }
  return {};
}

static int analyze_one_point_robustness(const Config& cfg,
                                        const std::vector<int>& published) {
  IsoscelesFreeSet state(cfg.n);
  state.reset(published);
  if (!state.verify()) throw std::runtime_error("Published seed failed verification");

  int global_min = 24;
  for (int p = 0; p < cfg.n * cfg.n; ++p) {
    if (state.contains(p)) continue;
    const auto edges = conflict_edges(state, p);
    auto cover = minimum_vertex_cover_up_to(edges, global_min - 1, cfg.n * cfg.n);
    if (edges.empty()) {
      global_min = 0;
      break;
    }
    if (!cover.empty()) global_min = std::min<int>(global_min, cover.size());
  }
  if (global_min == 24) throw std::runtime_error("Robustness search exceeded cover budget 23");

  long long attaining = 0;
  std::vector<std::pair<int, std::vector<int>>> witnesses;
  for (int p = 0; p < cfg.n * cfg.n; ++p) {
    if (state.contains(p)) continue;
    const auto edges = conflict_edges(state, p);
    auto cover = minimum_vertex_cover_up_to(edges, global_min, cfg.n * cfg.n);
    if (global_min == 0 ? edges.empty() : !cover.empty() && static_cast<int>(cover.size()) == global_min) {
      ++attaining;
      if (witnesses.size() < 25) witnesses.emplace_back(p, std::move(cover));
    }
  }

  std::ofstream out(cfg.output, std::ios::trunc);
  out << "n=" << cfg.n << "\nsize=" << published.size()
      << "\nminimum_removals_for_one_new_point=" << global_min
      << "\nnumber_of_outside_points_attaining_minimum=" << attaining << "\n";
  for (const auto& [p, cover] : witnesses) {
    out << "candidate=(" << p / cfg.n << ',' << p % cfg.n << ") remove=[";
    for (size_t i = 0; i < cover.size(); ++i) {
      if (i) out << ',';
      out << '(' << cover[i] / cfg.n << ',' << cover[i] % cfg.n << ')';
    }
    out << "]\n";
  }
  std::cout << "robustness n=" << cfg.n << " size=" << published.size()
            << " min_removals=" << global_min << " attaining=" << attaining
            << " output=" << cfg.output << "\n";
  return 0;
}

static void enumerate_covers_up_to_three(const std::vector<Edge>& edges, int budget,
                                         int total, std::vector<int>& chosen,
                                         std::vector<std::vector<int>>& covers) {
  if (edges.empty()) {
    std::vector<int> ordered = chosen;
    std::sort(ordered.begin(), ordered.end());
    covers.push_back(std::move(ordered));
    return;
  }
  if (budget == 0 || matching_lower_bound(edges, total) > budget) return;
  const auto [u, v] = edges.front();
  for (int selected : {u, v}) {
    std::vector<Edge> remaining;
    remaining.reserve(edges.size());
    for (const auto& edge : edges) {
      if (edge.first != selected && edge.second != selected) remaining.push_back(edge);
    }
    chosen.push_back(selected);
    enumerate_covers_up_to_three(remaining, budget - 1, total, chosen, covers);
    chosen.pop_back();
  }
}

static uint64_t triple_key(int a, int b, int c, int total) {
  int values[3] = {a, b, c};
  std::sort(values, values + 3);
  return (static_cast<uint64_t>(values[0]) * total + values[1]) * total + values[2];
}

static std::vector<int> decode_triple(uint64_t key, int total) {
  const int c = key % total;
  key /= total;
  const int b = key % total;
  const int a = key / total;
  return {a, b, c};
}

static bool find_four_additions(IsoscelesFreeSet& state, const std::vector<int>& candidates,
                                size_t start, std::vector<int>& chosen) {
  if (chosen.size() >= 4) return true;
  if (chosen.size() + candidates.size() - start < 4) return false;
  for (size_t i = start; i < candidates.size(); ++i) {
    const int p = candidates[i];
    if (!state.add(p)) continue;
    chosen.push_back(p);
    if (find_four_additions(state, candidates, i + 1, chosen)) return true;
    chosen.pop_back();
    state.remove(p);
  }
  return false;
}

static int analyze_three_removal_neighborhood(const Config& cfg,
                                              const std::vector<int>& published) {
  IsoscelesFreeSet original(cfg.n);
  original.reset(published);
  if (!original.verify()) throw std::runtime_error("Published seed failed verification");
  const int total = cfg.n * cfg.n;
  std::unordered_map<uint64_t, std::vector<int>> unlocked;

  for (int p = 0; p < total; ++p) {
    if (original.contains(p)) continue;
    const auto edges = conflict_edges(original, p);
    std::vector<std::vector<int>> covers;
    std::vector<int> chosen;
    enumerate_covers_up_to_three(edges, 3, total, chosen, covers);
    std::sort(covers.begin(), covers.end());
    covers.erase(std::unique(covers.begin(), covers.end()), covers.end());
    std::unordered_set<uint64_t> keys_for_p;
    for (const auto& cover : covers) {
      if (cover.size() == 3) {
        keys_for_p.insert(triple_key(cover[0], cover[1], cover[2], total));
      } else if (cover.size() == 2) {
        for (int q : published) {
          if (q != cover[0] && q != cover[1]) {
            keys_for_p.insert(triple_key(cover[0], cover[1], q, total));
          }
        }
      }
    }
    for (uint64_t key : keys_for_p) unlocked[key].push_back(p);
  }

  size_t max_unlocked = 0;
  long long triples_with_four_candidates = 0;
  std::vector<int> winning_removals, winning_additions;
  for (auto& [key, candidates] : unlocked) {
    std::sort(candidates.begin(), candidates.end());
    candidates.erase(std::unique(candidates.begin(), candidates.end()), candidates.end());
    max_unlocked = std::max(max_unlocked, candidates.size());
    if (candidates.size() < 4) continue;
    ++triples_with_four_candidates;
    const auto removals = decode_triple(key, total);
    std::vector<int> base;
    base.reserve(published.size() - 3);
    for (int p : published) {
      if (p != removals[0] && p != removals[1] && p != removals[2]) base.push_back(p);
    }
    IsoscelesFreeSet state(cfg.n);
    state.reset(base);
    std::vector<int> additions;
    if (find_four_additions(state, candidates, 0, additions)) {
      winning_removals = removals;
      winning_additions = additions;
      std::vector<int> solution = base;
      solution.insert(solution.end(), additions.begin(), additions.end());
      state.reset(solution);
      if (!state.verify()) throw std::runtime_error("Radius-three construction failed validation");
      write_solution(cfg.output, cfg.n, solution, cfg.seed, 0);
      std::cout << "RADIUS3_IMPROVED size=" << solution.size() << " removals=3 additions="
                << additions.size() << " output=" << cfg.output << "\n";
      return 0;
    }
  }

  std::ofstream out(cfg.output, std::ios::trunc);
  out << "n=" << cfg.n << "\nsize=" << published.size()
      << "\nremoval_triples_unlocking_at_least_one=" << unlocked.size()
      << "\nmaximum_individually_addable_after_three_removals=" << max_unlocked
      << "\ntriples_unlocking_at_least_four_individual_candidates="
      << triples_with_four_candidates << "\nfound_improvement=false\n";
  std::cout << "radius3 n=" << cfg.n << " triples=" << unlocked.size()
            << " max_unlocked=" << max_unlocked
            << " triples_with_four=" << triples_with_four_candidates
            << " improved=false output=" << cfg.output << "\n";
  return 0;
}

static uint64_t quadruple_key(int a, int b, int c, int d, int total) {
  int values[4] = {a, b, c, d};
  std::sort(values, values + 4);
  uint64_t key = values[0];
  for (int i = 1; i < 4; ++i) key = key * total + values[i];
  return key;
}

static std::vector<int> decode_quadruple(uint64_t key, int total) {
  std::vector<int> values(4);
  for (int i = 3; i >= 0; --i) {
    values[i] = key % total;
    key /= total;
  }
  return values;
}

static bool find_k_additions(IsoscelesFreeSet& state, const std::vector<int>& candidates,
                             size_t start, int target, std::vector<int>& chosen) {
  if (static_cast<int>(chosen.size()) >= target) return true;
  if (chosen.size() + candidates.size() - start < static_cast<size_t>(target)) return false;
  for (size_t i = start; i < candidates.size(); ++i) {
    const int p = candidates[i];
    if (!state.add(p)) continue;
    chosen.push_back(p);
    if (find_k_additions(state, candidates, i + 1, target, chosen)) return true;
    chosen.pop_back();
    state.remove(p);
  }
  return false;
}

static int analyze_four_removal_neighborhood(const Config& cfg,
                                             const std::vector<int>& published) {
  IsoscelesFreeSet original(cfg.n);
  original.reset(published);
  if (!original.verify()) throw std::runtime_error("Published seed failed verification");
  const int total = cfg.n * cfg.n;
  std::unordered_map<uint64_t, std::vector<int>> unlocked;

  for (int p = 0; p < total; ++p) {
    if (original.contains(p)) continue;
    const auto edges = conflict_edges(original, p);
    std::vector<std::vector<int>> covers;
    std::vector<int> chosen;
    enumerate_covers_up_to_three(edges, 4, total, chosen, covers);
    std::sort(covers.begin(), covers.end());
    covers.erase(std::unique(covers.begin(), covers.end()), covers.end());
    std::unordered_set<uint64_t> keys_for_p;
    for (const auto& cover : covers) {
      if (cover.size() == 4) {
        keys_for_p.insert(quadruple_key(cover[0], cover[1], cover[2], cover[3], total));
      } else if (cover.size() == 3) {
        for (int q : published) {
          if (std::find(cover.begin(), cover.end(), q) == cover.end()) {
            keys_for_p.insert(quadruple_key(cover[0], cover[1], cover[2], q, total));
          }
        }
      } else if (cover.size() == 2) {
        for (size_t i = 0; i < published.size(); ++i) {
          const int q = published[i];
          if (q == cover[0] || q == cover[1]) continue;
          for (size_t j = i + 1; j < published.size(); ++j) {
            const int r = published[j];
            if (r == cover[0] || r == cover[1]) continue;
            keys_for_p.insert(quadruple_key(cover[0], cover[1], q, r, total));
          }
        }
      }
    }
    for (uint64_t key : keys_for_p) unlocked[key].push_back(p);
    if (p % 1000 == 0) {
      std::cerr << "radius4 progress candidate=" << p << " removal_sets=" << unlocked.size() << "\n";
    }
  }

  size_t max_unlocked = 0;
  uint64_t max_key = 0;
  std::vector<int> max_candidates;
  long long sets_with_five_candidates = 0;
  for (auto& [key, candidates] : unlocked) {
    std::sort(candidates.begin(), candidates.end());
    candidates.erase(std::unique(candidates.begin(), candidates.end()), candidates.end());
    if (candidates.size() > max_unlocked) {
      max_unlocked = candidates.size();
      max_key = key;
      max_candidates = candidates;
    }
    if (candidates.size() < 5) continue;
    ++sets_with_five_candidates;
    const auto removals = decode_quadruple(key, total);
    std::vector<int> base;
    base.reserve(published.size() - 4);
    for (int point : published) {
      if (std::find(removals.begin(), removals.end(), point) == removals.end()) base.push_back(point);
    }
    IsoscelesFreeSet state(cfg.n);
    state.reset(base);
    std::vector<int> additions;
    if (find_k_additions(state, candidates, 0, 5, additions)) {
      std::vector<int> solution = base;
      solution.insert(solution.end(), additions.begin(), additions.end());
      state.reset(solution);
      if (!state.verify()) throw std::runtime_error("Radius-four construction failed validation");
      write_solution(cfg.output, cfg.n, solution, cfg.seed, 0);
      std::cout << "RADIUS4_IMPROVED size=" << solution.size() << " removals=4 additions="
                << additions.size() << " output=" << cfg.output << "\n";
      return 0;
    }
  }

  std::ofstream out(cfg.output, std::ios::trunc);
  out << "n=" << cfg.n << "\nsize=" << published.size()
      << "\nremoval_quadruples_unlocking_at_least_one=" << unlocked.size()
      << "\nmaximum_individually_addable_after_four_removals=" << max_unlocked
      << "\nquadruples_unlocking_at_least_five_individual_candidates="
      << sets_with_five_candidates << "\nfound_improvement=false\n";
  if (max_unlocked > 0) {
    const auto removals = decode_quadruple(max_key, total);
    out << "example_maximizing_removals=[";
    for (size_t i = 0; i < removals.size(); ++i) {
      if (i) out << ',';
      out << '(' << removals[i] / cfg.n << ',' << removals[i] % cfg.n << ')';
    }
    out << "]\nexample_unlocked_candidates=[";
    for (size_t i = 0; i < max_candidates.size(); ++i) {
      if (i) out << ',';
      out << '(' << max_candidates[i] / cfg.n << ',' << max_candidates[i] % cfg.n << ')';
    }
    out << "]\n";
  }
  std::cout << "radius4 n=" << cfg.n << " removal_sets=" << unlocked.size()
            << " max_unlocked=" << max_unlocked << " sets_with_five="
            << sets_with_five_candidates << " improved=false output=" << cfg.output << "\n";
  return 0;
}

static uint64_t encode_indices(const std::vector<int>& indices, int base) {
  uint64_t key = 0;
  for (int index : indices) key = key * base + index;
  return key;
}

static std::vector<int> decode_indices(uint64_t key, int length, int base) {
  std::vector<int> indices(length);
  for (int i = length - 1; i >= 0; --i) {
    indices[i] = key % base;
    key /= base;
  }
  return indices;
}

static std::vector<int> make_cover_inclusion_minimal(std::vector<int> cover,
                                                     const std::vector<Edge>& edges) {
  std::sort(cover.begin(), cover.end());
  cover.erase(std::unique(cover.begin(), cover.end()), cover.end());
  bool changed = true;
  while (changed) {
    changed = false;
    for (size_t i = 0; i < cover.size(); ++i) {
      const int removed = cover[i];
      bool still_covers = true;
      for (const auto& [a, b] : edges) {
        bool covered = false;
        for (int vertex : cover) {
          if (vertex != removed && (vertex == a || vertex == b)) {
            covered = true;
            break;
          }
        }
        if (!covered) {
          still_covers = false;
          break;
        }
      }
      if (still_covers) {
        cover.erase(cover.begin() + i);
        changed = true;
        break;
      }
    }
  }
  return cover;
}

static int analyze_five_removal_neighborhood(const Config& cfg,
                                             const std::vector<int>& published) {
  IsoscelesFreeSet original(cfg.n);
  original.reset(published);
  if (!original.verify()) throw std::runtime_error("Published seed failed verification");
  const int grid_total = cfg.n * cfg.n;
  const int m = published.size();
  std::vector<int> selected_index(grid_total, -1);
  for (int i = 0; i < m; ++i) selected_index[published[i]] = i;

  std::vector<std::unordered_map<uint64_t, std::vector<int>>> cover_maps(6);
  for (int p = 0; p < grid_total; ++p) {
    if (original.contains(p)) continue;
    const auto point_edges = conflict_edges(original, p);
    std::vector<Edge> edges;
    edges.reserve(point_edges.size());
    for (const auto& [a, b] : point_edges) {
      edges.emplace_back(selected_index[a], selected_index[b]);
    }
    std::vector<std::vector<int>> covers;
    std::vector<int> chosen;
    enumerate_covers_up_to_three(edges, 5, m, chosen, covers);
    std::vector<std::vector<int>> minimal;
    for (auto& cover : covers) {
      auto reduced = make_cover_inclusion_minimal(std::move(cover), edges);
      if (reduced.size() >= 2 && reduced.size() <= 5) minimal.push_back(std::move(reduced));
    }
    std::sort(minimal.begin(), minimal.end());
    minimal.erase(std::unique(minimal.begin(), minimal.end()), minimal.end());
    for (const auto& cover : minimal) {
      cover_maps[cover.size()][encode_indices(cover, m)].push_back(p);
    }
  }
  for (int size = 2; size <= 5; ++size) {
    for (auto& [key, candidates] : cover_maps[size]) {
      (void)key;
      std::sort(candidates.begin(), candidates.end());
      candidates.erase(std::unique(candidates.begin(), candidates.end()), candidates.end());
    }
    std::cerr << "radius5 minimal_covers_size_" << size << '=' << cover_maps[size].size() << "\n";
  }

  std::vector<int> candidate_stamp(grid_total, 0);
  int stamp = 0;
  long long evaluated = 0;
  size_t max_unlocked = 0;
  std::vector<int> max_removals, max_candidates;
  long long sets_with_six_candidates = 0;
  bool found = false;
  std::vector<int> found_solution;

  auto evaluate = [&](const std::vector<int>& removal_indices) {
    ++evaluated;
    ++stamp;
    if (stamp == 0) {
      std::fill(candidate_stamp.begin(), candidate_stamp.end(), 0);
      stamp = 1;
    }
    std::vector<int> candidates;
    for (int mask = 0; mask < 32; ++mask) {
      const int bits = __builtin_popcount(static_cast<unsigned>(mask));
      if (bits < 2) continue;
      std::vector<int> subset;
      subset.reserve(bits);
      for (int i = 0; i < 5; ++i) if (mask & (1 << i)) subset.push_back(removal_indices[i]);
      auto it = cover_maps[bits].find(encode_indices(subset, m));
      if (it == cover_maps[bits].end()) continue;
      for (int p : it->second) {
        if (candidate_stamp[p] == stamp) continue;
        candidate_stamp[p] = stamp;
        candidates.push_back(p);
      }
    }
    if (candidates.size() > max_unlocked) {
      max_unlocked = candidates.size();
      max_removals = removal_indices;
      max_candidates = candidates;
    }
    if (candidates.size() < 6 || found) return;
    ++sets_with_six_candidates;
    std::vector<uint8_t> removed(m, false);
    for (int index : removal_indices) removed[index] = true;
    std::vector<int> base;
    for (int i = 0; i < m; ++i) if (!removed[i]) base.push_back(published[i]);
    IsoscelesFreeSet state(cfg.n);
    state.reset(base);
    std::vector<int> additions;
    if (find_k_additions(state, candidates, 0, 6, additions)) {
      found_solution = base;
      found_solution.insert(found_solution.end(), additions.begin(), additions.end());
      state.reset(found_solution);
      if (!state.verify()) throw std::runtime_error("Radius-five construction failed validation");
      found = true;
    }
  };

  for (int cover_size = 2; cover_size <= 5 && !found; ++cover_size) {
    for (const auto& [key, candidate_list] : cover_maps[cover_size]) {
      (void)candidate_list;
      std::vector<int> removals = decode_indices(key, cover_size, m);
      std::vector<uint8_t> used(m, false);
      for (int index : removals) used[index] = true;
      const int extras_needed = 5 - cover_size;
      std::function<void(int, int)> add_extras = [&](int start, int need) {
        if (found) return;
        if (need == 0) {
          std::vector<int> ordered = removals;
          std::sort(ordered.begin(), ordered.end());
          evaluate(ordered);
          return;
        }
        for (int index = start; index <= m - need; ++index) {
          if (used[index]) continue;
          used[index] = true;
          removals.push_back(index);
          add_extras(index + 1, need - 1);
          removals.pop_back();
          used[index] = false;
        }
      };
      add_extras(0, extras_needed);
      if (evaluated % 1000000 < 32) {
        std::cerr << "radius5 evaluated=" << evaluated << " max_unlocked=" << max_unlocked << "\n";
      }
      if (found) break;
    }
  }

  if (found) {
    write_solution(cfg.output, cfg.n, found_solution, cfg.seed, 0);
    std::cout << "RADIUS5_IMPROVED size=" << found_solution.size()
              << " output=" << cfg.output << "\n";
    return 0;
  }

  std::ofstream out(cfg.output, std::ios::trunc);
  out << "n=" << cfg.n << "\nsize=" << published.size()
      << "\nminimal_covers_size_2=" << cover_maps[2].size()
      << "\nminimal_covers_size_3=" << cover_maps[3].size()
      << "\nminimal_covers_size_4=" << cover_maps[4].size()
      << "\nminimal_covers_size_5=" << cover_maps[5].size()
      << "\nremoval_quintuples_evaluated_with_multiplicity=" << evaluated
      << "\nmaximum_individually_addable_after_five_removals=" << max_unlocked
      << "\nquintuples_unlocking_at_least_six_individual_candidates="
      << sets_with_six_candidates << "\nfound_improvement=false\n";
  if (!max_removals.empty()) {
    out << "example_maximizing_removals=[";
    for (size_t i = 0; i < max_removals.size(); ++i) {
      if (i) out << ',';
      const int point = published[max_removals[i]];
      out << '(' << point / cfg.n << ',' << point % cfg.n << ')';
    }
    out << "]\nexample_unlocked_candidates=[";
    for (size_t i = 0; i < max_candidates.size(); ++i) {
      if (i) out << ',';
      out << '(' << max_candidates[i] / cfg.n << ',' << max_candidates[i] % cfg.n << ')';
    }
    out << "]\n";
  }
  std::cout << "radius5 n=" << cfg.n << " evaluated=" << evaluated
            << " max_unlocked=" << max_unlocked << " sets_with_six="
            << sets_with_six_candidates << " improved=false output=" << cfg.output << "\n";
  return 0;
}

struct DeepCandidate {
  int point = -1;
  std::vector<Edge> conflicts;
  std::vector<std::vector<int>> covers;
};

static int run_deep_exchange_search(const Config& cfg, const std::vector<int>& published) {
  IsoscelesFreeSet original(cfg.n);
  original.reset(published);
  if (!original.verify()) throw std::runtime_error("Published seed failed verification");
  const int grid_total = cfg.n * cfg.n;
  const int m = published.size();
  std::vector<int> selected_index(grid_total, -1);
  for (int i = 0; i < m; ++i) selected_index[published[i]] = i;

  std::vector<DeepCandidate> outside;
  outside.reserve(grid_total - m);
  for (int p = 0; p < grid_total; ++p) {
    if (original.contains(p)) continue;
    DeepCandidate candidate;
    candidate.point = p;
    for (const auto& [a, b] : conflict_edges(original, p)) {
      candidate.conflicts.emplace_back(selected_index[a], selected_index[b]);
    }
    std::vector<std::vector<int>> covers;
    std::vector<int> chosen;
    enumerate_covers_up_to_three(candidate.conflicts, 8, m, chosen, covers);
    for (auto& cover : covers) {
      auto reduced = make_cover_inclusion_minimal(std::move(cover), candidate.conflicts);
      if (reduced.size() >= 2 && reduced.size() <= 8) candidate.covers.push_back(std::move(reduced));
    }
    std::sort(candidate.covers.begin(), candidate.covers.end());
    candidate.covers.erase(std::unique(candidate.covers.begin(), candidate.covers.end()),
                           candidate.covers.end());
    if (candidate.covers.size() > 24) candidate.covers.resize(24);
    outside.push_back(std::move(candidate));
  }
  std::cerr << "deep precomputed_candidates=" << outside.size() << "\n";

  std::mt19937_64 rng(cfg.seed);
  auto unlocked_candidates = [&](const std::vector<uint8_t>& removed) {
    std::vector<int> result;
    for (size_t i = 0; i < outside.size(); ++i) {
      bool unlocked = true;
      for (const auto& [a, b] : outside[i].conflicts) {
        if (!removed[a] && !removed[b]) {
          unlocked = false;
          break;
        }
      }
      if (unlocked) result.push_back(i);
    }
    return result;
  };

  int best_margin = -m;
  int best_unlocked = 0;
  int best_removed_count = 0;
  int best_added_count = 0;
  std::vector<int> best_removal_indices, best_added_points;
  long long iterations = 0;
  const auto deadline = Clock::now() + std::chrono::seconds(cfg.seconds);

  auto try_repair = [&](const std::vector<uint8_t>& removed,
                        const std::vector<int>& unlocked_indices, int removal_count) {
    if (static_cast<int>(unlocked_indices.size()) <= best_added_count &&
        static_cast<int>(unlocked_indices.size()) <= removal_count) return false;
    std::vector<int> base;
    for (int i = 0; i < m; ++i) if (!removed[i]) base.push_back(published[i]);
    std::vector<int> order = unlocked_indices;
    const int attempts = std::min(80, 8 + static_cast<int>(order.size()) * 2);
    for (int attempt = 0; attempt < attempts; ++attempt) {
      std::shuffle(order.begin(), order.end(), rng);
      IsoscelesFreeSet state(cfg.n);
      state.reset(base);
      std::vector<int> additions;
      for (int index : order) {
        const int point = outside[index].point;
        if (state.add(point)) additions.push_back(point);
      }
      const int margin = static_cast<int>(additions.size()) - removal_count;
      if (margin > best_margin ||
          (margin == best_margin && static_cast<int>(additions.size()) > best_added_count)) {
        best_margin = margin;
        best_unlocked = unlocked_indices.size();
        best_removed_count = removal_count;
        best_added_count = additions.size();
        best_added_points = additions;
        best_removal_indices.clear();
        for (int i = 0; i < m; ++i) if (removed[i]) best_removal_indices.push_back(i);
        std::cerr << "DEEP_BEST seed=" << cfg.seed << " iteration=" << iterations
                  << " removed=" << removal_count << " unlocked=" << unlocked_indices.size()
                  << " compatible_added=" << additions.size() << " margin=" << margin << "\n";
      }
      if (margin > 0) {
        std::vector<int> solution = base;
        solution.insert(solution.end(), additions.begin(), additions.end());
        state.reset(solution);
        if (!state.verify()) throw std::runtime_error("Deep exchange construction failed validation");
        write_solution(cfg.output, cfg.n, solution, cfg.seed, iterations);
        std::cout << "DEEP_IMPROVED seed=" << cfg.seed << " size=" << solution.size()
                  << " removed=" << removal_count << " added=" << additions.size()
                  << " output=" << cfg.output << "\n";
        return true;
      }
    }
    return false;
  };

  while (Clock::now() < deadline) {
    const int removal_count = cfg.deep_radius > 0
        ? cfg.deep_radius
        : 6 + static_cast<int>(rng() % 23);  // Explore radii 6..28.
    std::vector<uint8_t> removed(m, false);
    std::vector<int> removal_indices;
    removal_indices.reserve(removal_count);

    // Seed fixed-radius-six searches with the best CP-SAT witness currently
    // known, which unlocks four points. Reflections and subsequent guided
    // swaps immediately explore its surrounding basin.
    if (removal_count == 6 && (rng() % 100) < 45) {
      const int witness_points[6][2] = {
          {26, 59}, {7, 48}, {73, 59}, {92, 48}, {96, 2}, {3, 2}};
      for (const auto& coordinates : witness_points) {
        const int point = coordinates[0] * cfg.n + coordinates[1];
        const int index = selected_index[point];
        if (index >= 0 && !removed[index]) {
          removed[index] = true;
          removal_indices.push_back(index);
        }
      }
    }

    for (int anchor_try = 0; anchor_try < 200 && removal_indices.empty(); ++anchor_try) {
      const auto& candidate = outside[rng() % outside.size()];
      if (candidate.covers.empty()) continue;
      const auto& cover = candidate.covers[rng() % candidate.covers.size()];
      if (static_cast<int>(cover.size()) > removal_count) continue;
      for (int index : cover) {
        if (!removed[index]) {
          removed[index] = true;
          removal_indices.push_back(index);
        }
      }
    }
    while (static_cast<int>(removal_indices.size()) < removal_count) {
      const int index = rng() % m;
      if (!removed[index]) {
        removed[index] = true;
        removal_indices.push_back(index);
      }
    }

    auto current_unlocked = unlocked_candidates(removed);
    int current_score = current_unlocked.size();
    if (try_repair(removed, current_unlocked, removal_count)) return 0;

    const int steps = 120 + removal_count * 8;
    for (int step = 0; step < steps && Clock::now() < deadline; ++step) {
      ++iterations;
      std::vector<uint8_t> proposal = removed;
      std::vector<int> proposal_indices = removal_indices;
      bool guided = (rng() % 100) < 78;
      if (guided) {
        const DeepCandidate* target = nullptr;
        const std::vector<int>* target_cover = nullptr;
        int best_missing = 99;
        for (int probe = 0; probe < 24; ++probe) {
          const auto& candidate = outside[rng() % outside.size()];
          for (const auto& cover : candidate.covers) {
            int missing = 0;
            for (int index : cover) missing += !proposal[index];
            if (missing < best_missing && missing <= removal_count) {
              best_missing = missing;
              target = &candidate;
              target_cover = &cover;
            }
          }
        }
        if (target && target_cover && best_missing > 0) {
          std::vector<int> missing;
          for (int index : *target_cover) if (!proposal[index]) missing.push_back(index);
          std::vector<int> removable_positions;
          for (size_t pos = 0; pos < proposal_indices.size(); ++pos) {
            if (std::find(target_cover->begin(), target_cover->end(), proposal_indices[pos]) ==
                target_cover->end()) removable_positions.push_back(pos);
          }
          std::shuffle(removable_positions.begin(), removable_positions.end(), rng);
          if (removable_positions.size() >= missing.size()) {
            for (size_t i = 0; i < missing.size(); ++i) {
              const int pos = removable_positions[i];
              proposal[proposal_indices[pos]] = false;
              proposal_indices[pos] = missing[i];
              proposal[missing[i]] = true;
            }
          }
        } else {
          guided = false;
        }
      }
      if (!guided) {
        const int swaps = 1 + rng() % 3;
        for (int k = 0; k < swaps; ++k) {
          const int pos = rng() % proposal_indices.size();
          int replacement = rng() % m;
          while (proposal[replacement]) replacement = rng() % m;
          proposal[proposal_indices[pos]] = false;
          proposal_indices[pos] = replacement;
          proposal[replacement] = true;
        }
      }

      auto proposal_unlocked = unlocked_candidates(proposal);
      const int proposal_score = proposal_unlocked.size();
      const double temperature = 0.35 + 2.0 * step / std::max(1, steps - 1);
      const bool accept = proposal_score >= current_score ||
          std::generate_canonical<double, 53>(rng) <
              std::exp((proposal_score - current_score) / temperature);
      if (accept) {
        removed = std::move(proposal);
        removal_indices = std::move(proposal_indices);
        current_score = proposal_score;
        current_unlocked = std::move(proposal_unlocked);
      }
      if (current_score > best_unlocked || iterations % 250 == 0) {
        if (try_repair(removed, current_unlocked, removal_count)) return 0;
      }
    }
  }

  std::ofstream out(cfg.output, std::ios::trunc);
  out << "n=" << cfg.n << "\nrecord_size=" << published.size()
      << "\nseed=" << cfg.seed << "\niterations=" << iterations
      << "\nbest_removed=" << best_removed_count
      << "\nbest_individually_unlocked=" << best_unlocked
      << "\nbest_compatible_added=" << best_added_count
      << "\nbest_margin=" << best_margin << "\nfound_improvement=false\n";
  out << "best_removals=[";
  for (size_t i = 0; i < best_removal_indices.size(); ++i) {
    if (i) out << ',';
    const int point = published[best_removal_indices[i]];
    out << '(' << point / cfg.n << ',' << point % cfg.n << ')';
  }
  out << "]\nbest_additions=[";
  for (size_t i = 0; i < best_added_points.size(); ++i) {
    if (i) out << ',';
    out << '(' << best_added_points[i] / cfg.n << ',' << best_added_points[i] % cfg.n << ')';
  }
  out << "]\n";
  std::cout << "deep seed=" << cfg.seed << " iterations=" << iterations
            << " best_removed=" << best_removed_count << " best_unlocked=" << best_unlocked
            << " best_added=" << best_added_count << " best_margin=" << best_margin
            << " improved=false output=" << cfg.output << "\n";
  return 0;
}

static bool add_group(IsoscelesFreeSet& state, const std::vector<int>& group) {
  for (int p : group) if (state.contains(p)) return false;
  std::vector<int> added;
  added.reserve(group.size());
  for (int p : group) {
    if (!state.add(p)) {
      for (auto it = added.rbegin(); it != added.rend(); ++it) state.remove(*it);
      return false;
    }
    added.push_back(p);
  }
  return true;
}

struct GroupCoverResult {
  bool feasible = false;
  std::vector<int> cover;
};

static GroupCoverResult group_conflict_cover(const IsoscelesFreeSet& state,
                                             const std::vector<int>& candidate,
                                             const std::vector<int>& group_of_point,
                                             int total_groups, int max_budget) {
  const int total_points = static_cast<int>(group_of_point.size());
  std::vector<uint8_t> is_new(total_points, false);
  std::vector<int> combined = state.points();
  for (int p : candidate) {
    is_new[p] = true;
    combined.push_back(p);
  }

  std::unordered_set<int> forced;
  std::unordered_set<uint64_t> edge_keys;
  for (int apex : combined) {
    std::unordered_map<int, std::vector<int>> by_distance;
    by_distance.reserve(combined.size() * 2);
    for (int q : combined) {
      if (q != apex) by_distance[state.dist2(apex, q)].push_back(q);
    }
    for (const auto& [distance, equidistant] : by_distance) {
      (void)distance;
      for (size_t i = 0; i < equidistant.size(); ++i) {
        for (size_t j = i + 1; j < equidistant.size(); ++j) {
          const int a = equidistant[i], b = equidistant[j];
          if (!is_new[apex] && !is_new[a] && !is_new[b]) continue;
          int gids[3];
          int count = 0;
          for (int p : {apex, a, b}) {
            if (is_new[p]) continue;
            const int gid = group_of_point[p];
            bool duplicate = false;
            for (int k = 0; k < count; ++k) duplicate |= gids[k] == gid;
            if (!duplicate) gids[count++] = gid;
          }
          if (count == 0) return {};
          if (count == 1) {
            forced.insert(gids[0]);
          } else {
            const int lo = std::min(gids[0], gids[1]);
            const int hi = std::max(gids[0], gids[1]);
            edge_keys.insert((static_cast<uint64_t>(lo) << 32) | static_cast<uint32_t>(hi));
          }
        }
      }
    }
  }

  if (static_cast<int>(forced.size()) > max_budget) return {};
  std::vector<Edge> edges;
  edges.reserve(edge_keys.size());
  for (uint64_t key : edge_keys) {
    const int a = static_cast<int>(key >> 32);
    const int b = static_cast<int>(key & 0xffffffffU);
    if (!forced.count(a) && !forced.count(b)) edges.emplace_back(a, b);
  }
  auto extra = minimum_vertex_cover_up_to(edges, max_budget - forced.size(), total_groups);
  if (!edges.empty() && extra.empty()) return {};

  GroupCoverResult result;
  result.feasible = true;
  result.cover.assign(forced.begin(), forced.end());
  result.cover.insert(result.cover.end(), extra.begin(), extra.end());
  return result;
}

static int run_symmetric(const Config& cfg, const std::vector<int>& published) {
  if (cfg.n % 2 != 0) throw std::runtime_error("Symmetric mode currently requires even n");
  std::mt19937_64 rng(cfg.seed);
  IsoscelesFreeSet state(cfg.n);
  state.reset(published);
  if (!state.verify()) throw std::runtime_error("Published seed failed verification");

  std::vector<std::vector<int>> groups;
  std::vector<int> group_of_point(cfg.n * cfg.n, -1);
  for (int x = 0; x < cfg.n / 2; ++x) {
    for (int y = 0; y < cfg.n / 2; ++y) {
      std::vector<int> group = {x * cfg.n + y, (cfg.n - 1 - x) * cfg.n + y,
                                x * cfg.n + (cfg.n - 1 - y),
                                (cfg.n - 1 - x) * cfg.n + (cfg.n - 1 - y)};
      const int gid = groups.size();
      for (int p : group) group_of_point[p] = gid;
      groups.push_back(std::move(group));
    }
  }
  for (const auto& group : groups) {
    int count = 0;
    for (int p : group) count += state.contains(p);
    if (count != 0 && count != 4) {
      throw std::runtime_error("Seed is not symmetric under both central-axis reflections");
    }
  }

  std::vector<int> best = state.points();
  std::vector<int> current = best;
  write_solution(cfg.output, cfg.n, best, cfg.seed, 0);
  std::cerr << "symmetric start seed=" << cfg.seed << " n=" << cfg.n
            << " published=" << published.size() << "\n";

  const auto deadline = Clock::now() + std::chrono::seconds(cfg.seconds);
  long long iteration = 0;
  long long last_improvement = 0;
  std::vector<double> priority(groups.size());

  while (Clock::now() < deadline) {
    ++iteration;
    state.reset(current);
    const int old_size = state.size();

    std::vector<int> active;
    for (size_t i = 0; i < groups.size(); ++i) if (state.contains(groups[i][0])) active.push_back(i);
    bool targeted = false;
    int forced_group = -1;
    std::vector<int> groups_to_remove;
    if (rng() % 100 < 35) {
      std::vector<int> outside;
      for (size_t i = 0; i < groups.size(); ++i) if (!state.contains(groups[i][0])) outside.push_back(i);
      std::shuffle(outside.begin(), outside.end(), rng);
      int best_cover_size = 99;
      const int probes = std::min<int>(28, outside.size());
      for (int i = 0; i < probes; ++i) {
        const int gid = outside[i];
        auto result = group_conflict_cover(state, groups[gid], group_of_point,
                                           groups.size(), 10);
        if (!result.feasible || static_cast<int>(result.cover.size()) >= best_cover_size) continue;
        best_cover_size = result.cover.size();
        forced_group = gid;
        groups_to_remove = std::move(result.cover);
        if (best_cover_size <= 2) break;
      }
      targeted = forced_group >= 0;
    }
    if (!targeted) {
      int ruin_groups;
      const int roll = rng() % 100;
      if (roll < 40) ruin_groups = 1 + rng() % 3;
      else if (roll < 85) ruin_groups = 4 + rng() % 8;
      else ruin_groups = 12 + rng() % 10;
      ruin_groups = std::min<int>(ruin_groups, active.size() - 1);
      std::shuffle(active.begin(), active.end(), rng);
      groups_to_remove.assign(active.begin(), active.begin() + ruin_groups);
    }
    for (int gid : groups_to_remove) {
      for (int p : groups[gid]) state.remove(p);
    }
    if (targeted && !add_group(state, groups[forced_group])) {
      throw std::runtime_error("Targeted symmetric move failed validation");
    }

    std::vector<int> candidates;
    for (size_t i = 0; i < groups.size(); ++i) if (!state.contains(groups[i][0])) candidates.push_back(i);
    const int repair_mode = rng() % 4;
    for (int i : candidates) {
      const int p = groups[i][0];
      const int x = p / cfg.n, y = p % cfg.n;
      const double noise = std::generate_canonical<double, 53>(rng);
      if (repair_mode == 0) priority[i] = noise;
      else if (repair_mode == 1) priority[i] = 0.45 * std::min(x, y) + noise;
      else if (repair_mode == 2) priority[i] = 0.12 * std::min(x, y) + noise;
      else priority[i] = -0.06 * std::min(x, y) + noise;
    }
    std::sort(candidates.begin(), candidates.end(), [&](int a, int b) {
      return priority[a] < priority[b];
    });
    for (int i : candidates) add_group(state, groups[i]);

    const int new_size = state.size();
    if (new_size > static_cast<int>(best.size())) {
      best = state.points();
      current = best;
      last_improvement = iteration;
      write_solution(cfg.output, cfg.n, best, cfg.seed, iteration);
      std::cerr << "SYMMETRIC_IMPROVED seed=" << cfg.seed << " iteration=" << iteration
                << " size=" << best.size() << "\n";
    } else {
      bool accept = new_size == old_size ? (rng() % 100 < 75) : new_size > old_size;
      if (new_size < old_size) {
        const double temperature = 1.2 + std::min(4.0, (iteration - last_improvement) / 3000.0);
        accept = std::generate_canonical<double, 53>(rng) < std::exp((new_size - old_size) / temperature);
      }
      if (accept && new_size + 12 >= static_cast<int>(best.size())) current = state.points();
    }
    if (iteration % 500 == 0) {
      current = best;
      std::cerr << "symmetric progress seed=" << cfg.seed << " iteration=" << iteration
                << " best=" << best.size() << "\n";
    }
  }

  state.reset(best);
  const bool valid = state.verify();
  write_solution(cfg.output, cfg.n, best, cfg.seed, iteration);
  std::cout << "symmetric seed=" << cfg.seed << " n=" << cfg.n << " size=" << best.size()
            << " iterations=" << iteration << " valid=" << (valid ? "true" : "false")
            << " output=" << cfg.output << "\n";
  return valid ? 0 : 2;
}

int main(int argc, char** argv) {
  try {
    const Config cfg = parse_args(argc, argv);
    std::mt19937_64 rng(cfg.seed);
    std::vector<int> published = load_seed(cfg);
    if (cfg.deep) return run_deep_exchange_search(cfg, published);
    if (cfg.analyze5) return analyze_five_removal_neighborhood(cfg, published);
    if (cfg.analyze4) return analyze_four_removal_neighborhood(cfg, published);
    if (cfg.analyze3) return analyze_three_removal_neighborhood(cfg, published);
    if (cfg.analyze) return analyze_one_point_robustness(cfg, published);
    if (cfg.symmetric) return run_symmetric(cfg, published);
    IsoscelesFreeSet state(cfg.n);
    state.reset(published);
    if (!state.verify()) throw std::runtime_error("Published seed failed verification");

    std::vector<int> best = state.points();
    std::vector<int> current = best;
    write_solution(cfg.output, cfg.n, best, cfg.seed, 0);
    std::cerr << "start seed=" << cfg.seed << " n=" << cfg.n
              << " published=" << published.size() << "\n";

    std::vector<int> universe(cfg.n * cfg.n);
    std::iota(universe.begin(), universe.end(), 0);
    std::vector<double> priority(universe.size());
    const auto deadline = Clock::now() + std::chrono::seconds(cfg.seconds);
    long long iteration = 0;
    long long last_improvement = 0;

    while (Clock::now() < deadline) {
      ++iteration;
      state.reset(current);
      const int old_size = state.size();

      int ruin = 1;
      const uint64_t mode_roll = rng() % 100;
      if (mode_roll < 20) ruin = 1 + static_cast<int>(rng() % 3);
      else if (mode_roll < 70) ruin = 3 + static_cast<int>(rng() % 7);
      else ruin = 8 + static_cast<int>(rng() % 13);
      ruin = std::min(ruin, state.size() - 1);

      std::vector<int> removal;
      removal.reserve(ruin);
      int forced_candidate = -1;
      const int ruin_mode = static_cast<int>(rng() % 5);
      if (ruin_mode == 4) {
        // Pick an outside point whose conflicts can be killed by a small exact
        // vertex cover, yielding a targeted swap rather than a blind ruin.
        std::vector<int> outside;
        outside.reserve(universe.size() - state.size());
        for (int p : universe) if (!state.contains(p)) outside.push_back(p);
        std::shuffle(outside.begin(), outside.end(), rng);
        int best_cover_size = 99;
        const int probes = std::min<int>(48, outside.size());
        for (int i = 0; i < probes; ++i) {
          const int p = outside[i];
          const auto edges = conflict_edges(state, p);
          auto cover = minimum_vertex_cover_up_to(edges, 8, cfg.n * cfg.n);
          if ((!edges.empty() && cover.empty()) || static_cast<int>(cover.size()) >= best_cover_size) continue;
          best_cover_size = static_cast<int>(cover.size());
          forced_candidate = p;
          removal = std::move(cover);
          if (best_cover_size <= 2) break;
        }
      }
      if (removal.empty() && forced_candidate < 0 && ruin_mode == 0) {
        std::sample(state.points().begin(), state.points().end(),
                    std::back_inserter(removal), ruin, rng);
      } else if (removal.empty() && forced_candidate < 0) {
        const auto snapshot = state.points();
        const int anchor = snapshot[rng() % snapshot.size()];
        std::vector<std::pair<double, int>> ranked;
        ranked.reserve(snapshot.size());
        const int ax = anchor / cfg.n, ay = anchor % cfg.n;
        for (int p : snapshot) {
          const int x = p / cfg.n, y = p % cfg.n;
          double score = 0.0;
          if (ruin_mode == 1) score = state.dist2(anchor, p);          // Local patch.
          else if (ruin_mode == 2) score = std::abs(x - ax) + (rng() % 9) * 0.01;  // Columns.
          else score = std::abs(y - ay) + (rng() % 9) * 0.01;         // Rows.
          ranked.emplace_back(score, p);
        }
        std::nth_element(ranked.begin(), ranked.begin() + ruin, ranked.end());
        for (int i = 0; i < ruin; ++i) removal.push_back(ranked[i].second);
      }
      for (int p : removal) state.remove(p);
      if (forced_candidate >= 0 && !state.add(forced_candidate)) {
        throw std::runtime_error("Targeted vertex-cover move failed validation");
      }

      std::vector<int> candidates;
      candidates.reserve(universe.size() - state.size());
      for (int p : universe) if (!state.contains(p)) candidates.push_back(p);

      const int repair_mode = static_cast<int>(rng() % 6);
      for (int p : candidates) {
        const double noise = std::generate_canonical<double, 53>(rng);
        const int b = border_distance(p, cfg.n);
        if (repair_mode == 0) priority[p] = noise;                    // Pure random.
        else if (repair_mode == 1) priority[p] = 0.35 * b + noise;   // Strong boundary bias.
        else if (repair_mode == 2) priority[p] = 0.10 * b + noise;   // Mild boundary bias.
        else if (repair_mode == 3) priority[p] = -0.08 * b + noise;  // Occasionally probe interior.
        else if (repair_mode == 4) {
          const int x = p / cfg.n, y = p % cfg.n;
          priority[p] = 0.12 * b + 0.02 * std::min(std::abs(x - y), std::abs(x + y - cfg.n + 1)) + noise;
        } else {
          const int x = p / cfg.n, y = p % cfg.n;
          int partners = 0;
          partners += state.contains((cfg.n - 1 - x) * cfg.n + y);
          partners += state.contains(x * cfg.n + (cfg.n - 1 - y));
          partners += state.contains((cfg.n - 1 - x) * cfg.n + (cfg.n - 1 - y));
          priority[p] = -0.85 * partners + 0.10 * b + noise;
        }
      }
      std::sort(candidates.begin(), candidates.end(), [&](int a, int b) {
        return priority[a] < priority[b];
      });
      for (int p : candidates) state.add(p);

      const int new_size = state.size();
      if (new_size > static_cast<int>(best.size())) {
        best = state.points();
        current = best;
        last_improvement = iteration;
        write_solution(cfg.output, cfg.n, best, cfg.seed, iteration);
        std::cerr << "IMPROVED seed=" << cfg.seed << " iteration=" << iteration
                  << " size=" << best.size() << "\n";
      } else {
        bool accept = false;
        if (new_size > old_size) accept = true;
        else if (new_size == old_size) accept = (rng() % 100) < 70;
        else {
          const double temperature = 0.35 + std::min(1.5, (iteration - last_improvement) / 20000.0);
          const double probability = std::exp((new_size - old_size) / temperature);
          accept = std::generate_canonical<double, 53>(rng) < probability;
        }
        if (accept && new_size + 4 >= static_cast<int>(best.size())) current = state.points();
      }

      if (iteration % 2500 == 0) {
        current = best;
        std::cerr << "progress seed=" << cfg.seed << " iteration=" << iteration
                  << " current=" << current.size() << " best=" << best.size() << "\n";
      }
    }

    state.reset(best);
    const bool valid = state.verify();
    write_solution(cfg.output, cfg.n, best, cfg.seed, iteration);
    std::cout << "seed=" << cfg.seed << " n=" << cfg.n << " size=" << best.size()
              << " iterations=" << iteration << " valid=" << (valid ? "true" : "false")
              << " output=" << cfg.output << "\n";
    return valid ? 0 : 2;
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << "\n";
    return 1;
  }
}
