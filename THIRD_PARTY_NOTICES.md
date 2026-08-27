# Third-party material and provenance

This inventory is a publication preflight aid, not legal advice and not a
license for the new material in this workspace.

## AlphaEvolve problem repository

The fixed `64 x 64` and `100 x 100` configurations, and the notebook from
which they are parsed, originate in Google DeepMind's public
`alphaevolve_repository_of_problems`, pinned here at commit
`8f447457957deac61e28bf1676746f0753b3b2f8`.

The upstream README states:

- copyright 2025 Google LLC;
- software is Apache License 2.0;
- other material is Creative Commons Attribution 4.0 International;
- the repository should be cited as Bogdan Georgiev, Javier Gomez-Serrano,
  Terence Tao, and Adam Zsolt Wagner, *Mathematical exploration and discovery
  at scale* (2025), arXiv:2511.02864.

The upstream license text remains at
`alphaevolve_repository_of_problems/LICENSE`. A public artifact that
redistributes upstream files must preserve the applicable license and
attribution notices. A smaller clean release may instead ship the attributed
coordinates, their hashes, and a deterministic retrieval/extraction script.

## Solvers and proof checkers

The artifact calls third-party software including CaDiCaL, DRAT-trim,
python-sat, OR-Tools, and NumPy. Their source code and licenses are not replaced
by any license selected for the new scripts. A frozen public release should
list exact versions/commits and retain every bundled tool's own license and
notice files.

## New work

No license has yet been selected for the new manuscript, scripts, generated
CNFs, proof traces, or metadata. That choice is reserved for the human rights
holder and is a mandatory publication gate.
