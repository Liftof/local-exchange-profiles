# Consequences of the exact exchange profile through radius eight

Working note, 27 August 2026. These deductions are elementary consequences of
the audited exact computational profile; no claim of literature novelty is made.

Let `H` be the 3-uniform no-isosceles hypergraph on the `100 x 100` grid and
let `S` be the published 164-point independent set. For an independent set
`X`, write

```text
r(X) = |S \ X|,      a(X) = |X \ S|.
```

The exact genuine-exchange profile currently known is

```text
r       0  1  2  3  4  5  6  7  8
e_S(r)  0  0  1  1  2  3  4  5  6.
```

By definition, every independent `X` with `r(X)=r` satisfies
`a(X)<=e_S(r)`.

## 1. A tight local size envelope and a solver cut

For every independent `X` with `r(X)<=8`,

```text
|X| = 164 - r(X) + a(X) <= 164 - r(X) + e_S(r(X)).
```

Thus the exact shell envelope is

| `r(X)` | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| maximum `|X|` | 164 | 163 | 163 | 162 | 162 | 162 | 162 | 162 | 162 |

Each entry is attained by a witness for `e_S(r)`, so this envelope is tight on
every displayed shell.

It follows that any `X != S` with `|X|>=164` has `r(X)>=9`, equivalently

```text
|X intersect S| <= 155.                                      (1)
```

Equation (1) is a useful incumbent cut. In a SAT, MILP, or CP model with
binary point variables `x_v`, any feasibility subproblem seeking an
improvement (`sum_v x_v >= 165`) may safely add

```text
sum_{s in S} x_s <= 155.
```

The same cut is valid when searching for a distinct alternative of size 164,
provided `S` itself is explicitly excluded. It is not an unconditional cut
for smaller feasible sets.

In a removal-first destroy-and-repair enumeration, the cut eliminates all
record-removal shells zero through eight before any repair search. Their
number is

```text
sum_{r=0}^8 binom(164,r) = 11,494,182,836,236.
```

This number counts removal subsets, not necessarily nodes of a modern solver;
the aggregate overlap inequality is preferable to enumerating the associated
no-goods.

## 2. A general token-addition/removal crossing theorem

Consider the token-addition/removal (TAR) reconfiguration graph: vertices are
independent sets, and an edge adds or deletes one grid point. Let

```text
S = X_0, X_1, ..., X_m = T
```

be a TAR path, and suppose `r(T)>=R`.

### Theorem

Every such path contains a set of size at most

```text
|S| - B_cross(R),

B_cross(R) = max(0, max_{0 <= r < R} (r + 1 - e_S(r))).      (2)
```

### Proof

Put `r_i=|S\X_i|`. We have `r_0=0` and `r_m>=R`. A TAR move changes `r_i`
by `-1`, `0`, or `1`. Consequently, for each integer `r` with `0<=r<R`,
there is an index `i=i(r)` such that

```text
r_i=r,             r_{i+1}=r+1.
```

For example, one may choose the index immediately preceding the first visit
to level `r+1`. The move `X_i -> X_{i+1}` cannot be an outsider move: it is
the deletion of one point of `S` that was still present in `X_i`. In
particular,

```text
|X_{i+1}|=|X_i|-1.
```

The independent predecessor `X_i` has `r` deleted original points and at most
`e_S(r)` outsiders. Therefore

```text
|X_{i+1}| = |S|-r+a(X_i)-1
            <= |S|-(r+1)+e_S(r)
             = |S|-(r+1-e_S(r)).
```

There is such a (possibly different) crossing state for every `r<R`. Choosing
an `r` that maximizes `r+1-e_S(r)` proves (2). Notice that this uses the state
*after* the upward crossing; bounding an arbitrary state on each shell would
miss the final `+1`.

### Application to `S`

Any distinct independent `T` with `|T|>=164` has `r(T)>=9`. For `R=9`, the
crossing deficits are

```text
r                  0  1  2  3  4  5  6  7  8
r+1-e_S(r)         1  2  2  3  3  3  3  3  3,
```

so `B_cross(9)=3`. Consequently:

> Every TAR path from `S` to any other independent set of size at least 164
> must visit a set of size at most 161.

Equivalently, `S` and every other independent set of size at least 164 lie in
different connected components of the TAR graph restricted to sets of size at
least 162. This is a dynamic three-point valley, not merely a Hamming-distance
statement.

### Check on the `64 x 64` construction

For the published 112-point set, the exact profile through radius seven is

```text
r       0  1  2  3  4  5  6  7
e_S(r)  0  1  2  2  4  4  5  5.
```

The shell maxima `112-r+e_S(r)` are

```text
112, 112, 112, 111, 112, 111, 111, 110.
```

Thus any improvement of size at least 113 has at least eight deleted original
points. With `R=8`, the crossing deficits are

```text
1, 1, 1, 2, 1, 2, 2, 3.
```

The theorem therefore forces every TAR path from this 112-point set to an
improvement to visit a set of size at most `112-3=109`. This conclusion is
specific to improvements: the profile permits equal-size configurations in
several smaller shells.

## 3. Exact local TAR component structure

Let `TAR_k` denote the TAR graph induced by independent sets of size at least
`k`.

### Proposition

The connected component of `S` in `TAR_163` is exactly the star

```text
{S} union {S \ {s} : s in S}.
```

It has one center and 164 leaves.

### Proof

Since `e_S(0)=0`, no outside point can be added directly to `S`. Hence the only
moves from `S` delete one of its 164 points. A leaf `S\{s}` has size 163, so
another deletion is forbidden in `TAR_163`. Adding `s` returns to `S`, while
adding an outside point would contradict `e_S(1)=0`. Thus the listed star has
no further incident edge inside `TAR_163`.

Paths through size 162 change the picture, so the analogous component in
`TAR_162` is not just this star. It nevertheless has the following exact
description. It contains:

1. every independent state of size at least 162 with `r<=2`; and
2. exactly those states `(S\R) union {p}` with `|R|=3` for which some
   `s in R` makes `(S\(R\{s})) union {p}` independent.

There are no other states in the component. To prove the first inclusion,
delete the at most two members of `R` and then add the (at most one) outsider;
all intermediate states are independent and have size at least 162. For a
state in item 2, use the same path to its indicated radius-two predecessor and
then delete `s`.

Conversely, the first crossing from three to four deletions would, using
`e_S(3)=1`, produce a state of size at most
`164-4+1=161`; hence the component contains no state with `r>=4`. At `r=3`,
the threshold 162 and `e_S(3)=1` force the state to have exactly one outsider
and size exactly 162. Any incident edge retained by `TAR_162` must add a point:
adding another outsider would contradict `e_S(3)=1`, so the added point must
restore some `s in R` and give precisely the radius-two predecessor in item 2.
This also accounts for arbitrary detours and reinsertions along a path.

For fixed-size token jumping on 164-point independent sets, every distinct
configuration is at least nine token jumps from `S`, because each jump can
delete at most one previously retained point of `S`.

## 4. What can and cannot be inferred at radius nine

The exchange profile is monotone:

```text
e_S(r+1) >= e_S(r).
```

To prove this, take a witness `(R,A)` for `e_S(r)` and delete any additional
point of `S\R`; the same additions remain valid. Hence the current profile
gives the safe but weak lower bound

```text
e_S(9) >= 6.
```

There is no valid upper bound on `e_S(9)` obtained merely by extending the
observed pattern `e_S(r)=r-2` for `4<=r<=8`: monotonicity does not imply
concavity or a one-step Lipschitz bound. In particular, the data do not rule
out a large jump at radius nine.

The next improvement decision is exactly

```text
e_S(9) >= 10.
```

A subsequent bounded computation, documented in `radius9_FRONTIER.md`, did not
decide this question. It did produce a direct exact-integer witness for
`u_S(9)>=7`. On the representative removal mask all seven unlocked outsiders
are pairwise compatible, but `(4,98)`, `(75,81)`, and `(77,99)` form one
all-outsider isosceles triple, so that particular seven-point list has maximum
compatible subset six. This does not improve the global lower bound
`e_S(9)>=6` and gives no upper bound.

## Scope

The results above concern the local exchange and reconfiguration landscape
around this particular 164-point set. They do not prove global optimality,
connectedness at threshold 161, or any upper bound for `e_S(9)` beyond the
trivial finite-grid bound. The TAR theorem and overlap cut are rigorous given
the exact profile, but their novelty relative to the reconfiguration and
integer-programming literature has not been assessed.

As an edge-case regression, `audit/verify_tar_transition_theorem.py` checks the
theorem for every hereditary family on ground sets of size at most four, every
choice of base set, and every endpoint/radius pair: 197 families, 1,439 base
sets, and 44,056 assertions. This finite check supports the implementation and
indexing conventions; it does not replace the proof.
