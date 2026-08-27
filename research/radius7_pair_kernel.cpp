#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

struct Mask {
  std::array<std::uint64_t, 3> w{};
};

static Mask united(const Mask& a, const Mask& b) {
  return {{{a.w[0] | b.w[0], a.w[1] | b.w[1], a.w[2] | b.w[2]}}};
}

static int population(const Mask& a) {
  return __builtin_popcountll(a.w[0]) + __builtin_popcountll(a.w[1]) +
         __builtin_popcountll(a.w[2]);
}

static bool less_mask(const Mask& a, const Mask& b) {
  if (a.w[2] != b.w[2]) return a.w[2] < b.w[2];
  if (a.w[1] != b.w[1]) return a.w[1] < b.w[1];
  return a.w[0] < b.w[0];
}

template <class T>
static void read_exact(std::ifstream& in, T& value) {
  in.read(reinterpret_cast<char*>(&value), sizeof(value));
  if (!in) throw std::runtime_error("truncated binary input");
}

struct Candidate {
  std::uint16_t x{}, y{};
  std::vector<Mask> covers;
  int minimum = 99;
  bool all_radius = false;
};

static bool compatible(const Candidate& a, const Candidate& b, const Mask& forced,
                       int radius) {
  if (population(forced) > radius) return false;

  // If every cover on both sides already has size r, their union can have
  // size <= r only when the masks are identical.  Sorted intersection turns
  // the dominant r=8/r=8 case from quadratic into linear time.
  if (a.all_radius && b.all_radius) {
    std::size_t i = 0, j = 0;
    while (i < a.covers.size() && j < b.covers.size()) {
      if (!less_mask(a.covers[i], b.covers[j]) && !less_mask(b.covers[j], a.covers[i])) {
        if (population(united(a.covers[i], forced)) <= radius) return true;
        ++i;
        ++j;
      } else if (less_mask(a.covers[i], b.covers[j])) {
        ++i;
      } else {
        ++j;
      }
    }
    return false;
  }

  // With no forced record point, any two minimum covers whose sizes sum to at
  // most r are immediately compatible.
  if (population(forced) == 0 && a.minimum + b.minimum <= radius) return true;

  const Candidate* left = &a;
  const Candidate* right = &b;
  if (left->covers.size() > right->covers.size()) std::swap(left, right);
  for (const Mask& x : left->covers) {
    const Mask partial = united(x, forced);
    if (population(partial) > radius) continue;
    for (const Mask& y : right->covers) {
      if (population(united(partial, y)) <= radius) return true;
    }
  }
  return false;
}

int main(int argc, char** argv) {
  if (argc != 3) {
    std::cerr << "usage: radius7_pair_kernel INPUT.bin OUTPUT.json\n";
    return 2;
  }
  const auto started = std::chrono::steady_clock::now();
  std::ifstream in(argv[1], std::ios::binary);
  if (!in) throw std::runtime_error("cannot open input");
  char magic[4];
  in.read(magic, 4);
  if (std::string(magic, 4) != "RPC1") throw std::runtime_error("bad magic");
  std::uint32_t grid_n, radius, record_size, candidate_count;
  read_exact(in, grid_n); read_exact(in, radius); read_exact(in, record_size); read_exact(in, candidate_count);
  char digest_chars[64];
  in.read(digest_chars, 64);
  const std::string digest(digest_chars, 64);

  std::vector<Candidate> candidates(candidate_count);
  std::uint64_t total_covers = 0;
  for (Candidate& candidate : candidates) {
    read_exact(in, candidate.x); read_exact(in, candidate.y);
    std::uint32_t count; read_exact(in, count);
    candidate.covers.resize(count);
    candidate.all_radius = true;
    for (Mask& mask : candidate.covers) {
      read_exact(in, mask.w[0]); read_exact(in, mask.w[1]); read_exact(in, mask.w[2]);
      const int size = population(mask);
      candidate.minimum = std::min(candidate.minimum, size);
      candidate.all_radius = candidate.all_radius && size == static_cast<int>(radius);
    }
    std::sort(candidate.covers.begin(), candidate.covers.end(), less_mask);
    total_covers += count;
  }
  std::uint32_t required_count; read_exact(in, required_count);
  std::unordered_map<std::uint64_t, Mask> required;
  required.reserve(required_count * 2);
  for (std::uint32_t z = 0; z < required_count; ++z) {
    std::uint32_t a, b; Mask mask;
    read_exact(in, a); read_exact(in, b);
    read_exact(in, mask.w[0]); read_exact(in, mask.w[1]); read_exact(in, mask.w[2]);
    required.emplace(static_cast<std::uint64_t>(a) * candidate_count + b, mask);
  }

  int threads = 1;
#ifdef _OPENMP
  threads = omp_get_max_threads();
#endif
  std::vector<std::vector<std::pair<std::uint32_t, std::uint32_t>>> local(threads);
#pragma omp parallel for schedule(dynamic, 1)
  for (std::int64_t i = 0; i < static_cast<std::int64_t>(candidate_count); ++i) {
    int thread = 0;
#ifdef _OPENMP
    thread = omp_get_thread_num();
#endif
    auto& output = local[thread];
    for (std::uint32_t j = i + 1; j < candidate_count; ++j) {
      const auto found = required.find(static_cast<std::uint64_t>(i) * candidate_count + j);
      const Mask empty{};
      const Mask& forced = found == required.end() ? empty : found->second;
      if (compatible(candidates[i], candidates[j], forced, radius)) output.emplace_back(i, j);
    }
  }
  std::vector<std::pair<std::uint32_t, std::uint32_t>> pairs;
  std::size_t pair_count = 0;
  for (const auto& part : local) pair_count += part.size();
  pairs.reserve(pair_count);
  for (auto& part : local) pairs.insert(pairs.end(), part.begin(), part.end());
  std::sort(pairs.begin(), pairs.end());

  const std::uint64_t tested = static_cast<std::uint64_t>(candidate_count) * (candidate_count - 1) / 2;
  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
  std::ofstream out(argv[2]);
  out << "{\"format\":\"radius-pair-compatibility-v1\",\"n\":" << grid_n
      << ",\"radius\":" << radius << ",\"record_size\":" << record_size
      << ",\"record_sha256\":\"" << digest << "\",\"eligible_candidates\":[";
  for (std::size_t i = 0; i < candidates.size(); ++i) {
    if (i) out << ',';
    out << '[' << candidates[i].x << ',' << candidates[i].y << ']';
  }
  out << "],\"eligible_candidate_count\":" << candidate_count
      << ",\"pairs_tested\":" << tested << ",\"compatible_pair_count\":" << pairs.size()
      << ",\"incompatible_pair_count\":" << tested - pairs.size()
      << ",\"pairs_with_forced_record_removals\":" << required_count
      << ",\"compatible_pairs\":[";
  for (std::size_t i = 0; i < pairs.size(); ++i) {
    if (i) out << ',';
    out << '[' << pairs[i].first << ',' << pairs[i].second << ']';
  }
  out << "],\"build_seconds\":" << seconds << "}\n";
  std::cout << "candidates=" << candidate_count << " covers=" << total_covers
            << " tested=" << tested << " compatible=" << pairs.size()
            << " threads=" << threads << " seconds=" << seconds << " output=" << argv[2] << "\n";
}
