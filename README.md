# Exact local exchange profiles for no-isosceles grid sets

This repository accompanies Pierre-Baptiste Borges, *Exact Local Exchange
Profiles and Reconfiguration Barriers for Isosceles-Triangle-Free Grid Sets*
(2026).

The paper introduces individual-unlock and compatible-exchange profiles around
a fixed hypergraph independent set, derives a token-addition/removal barrier,
and computes exact local profiles for the public AlphaEvolve 64 by 64 and
100 by 100 grid configurations.

The principal 100 by 100 result is that the public 164-point configuration is
locally isolated from every distinct set of equal or larger size through eight
deletions. Every distinct equal-size configuration is therefore at symmetric
difference at least 18, every strict improvement is at distance at least 19,
and every token-addition/removal path to a distinct set of size at least 164
visits a set of size at most 161. These statements do not prove global
optimality of 164.

Evidence levels are deliberately separated:

- radius six: independently regenerated CNF and verified DRAT proof;
- radius seven: direct witness, independently regenerated core CNF, and
  verified DRAT proof;
- radius eight: direct witness and independently audited exhaustive C++
  computation, without a DRAT/LRAT trace.

The complete frozen artifact, including the 292 MB radius-six proof trace, is
attached to the corresponding GitHub release. Start with `research/README.md`
and `paper/main.pdf`. SHA-256 identities and one-command replay instructions
are included in the artifact.

## Citation

```text
Pierre-Baptiste Borges. Exact Local Exchange Profiles and Reconfiguration
Barriers for Isosceles-Triangle-Free Grid Sets. 2026.
```
