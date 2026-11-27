---
id: ggs_transmission_matrix
title: Generalized Gerchberg-Saxton (GGS) retrieval of the transmission matrix
source: "Huang et al., Generalizing the Gerchberg-Saxton algorithm for retrieving complex optical transmission matrices, Photonics Research 9(1), 34 (2021), Eqs. 1-4, Sec. 2, Fig. 2"
tags: [transmission matrix, calibration, phase retrieval, ggs, gerchberg-saxton, intensity only, gamma]
---
Probe the medium with L random phase-only masks, grouped in the probing matrix P (L x N,
entries exp(i theta), theta uniform in [0, 2pi); Eq. 1). The target-plane field is
E = P X^T (Eq. 2), X being the unknown TM (M x N); the camera gives |E| (L x M).

Iteration f (Eqs. 3-4), with X~_f the estimate of X:
  E~_f = |E|^n (elementwise) * exp(i Arg(P X~_{f-1}^T)),
  X~_f = (P^+ E~_f)^T,   P^+ = pseudo-inverse of P.
Note: Eq. 3 is printed with |E|; the exponent n ("|E|^n is used to replace |E|") is
introduced in the text of Sec. 2.

Stopping (Sec. 2): a row stops when the correlation between X~_f and X~_{f-2} exceeds
99.9999% (f-2, not f-1, because of a period-2 oscillation), or after m iterations
(m = 1000 by default). Correlations are computed row by row and converged rows leave the
iteration. In GGS 2-1 at N = 1296 the two steps take ~287 and ~34 iterations (Sec. 5).

Variants (Sec. 2): GGS 1 (n = 1, the direct algorithm), GGS 2 (n = 2), GGS 2-1 (first
n = 2, then n = 1). The exponent acts like artificial "heat" in simulated annealing and
helps escape local optima. gamma = L/N: GGS 1 needs about 7N masks; GGS 2-1 works with 4N.

Numbers (noiseless UTC simulations): at N = 400, gamma = 4 the enhancement reaches 99.1%
(GGS 2-1), 87.1% (GGS 2) and 14.3% (GGS 1) of the theoretical value (Fig. 2a); the GGS 1
and GGS 2 curves cross near gamma = 6. At gamma = 4, GGS 2-1 gives 98.0-98.9% for
N = 64...1296 (Fig. 2c). GGS 1 at N = 1296: often trapped at gamma = 4; ~76% of runs near
theory at gamma = 6 and 95% at gamma = 7 (Fig. 2d).
