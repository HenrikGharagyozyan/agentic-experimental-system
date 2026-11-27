---
id: ggs_transmission_matrix
title: Generalized Gerchberg-Saxton (GGS) retrieval of the transmission matrix
source: "Huang et al., Generalizing the Gerchberg-Saxton algorithm for retrieving complex optical transmission matrices, Photonics Research 9(1), 34 (2021), Eqs. 1-4"
tags: [transmission matrix, calibration, phase retrieval, ggs, gerchberg-saxton, intensity only, gamma]
---
A camera measures only intensities, so T must be retrieved without a reference beam.
Probe with L random phase-only masks P (L x N, entries exp(i theta), theta in [0, 2pi));
measure amplitudes |E| = sqrt(I) (L x M). With X the estimate of T:
  E_f = |E|^n (elementwise) * exp(i Arg(P X_{f-1}^T)),   X_f = (P^+ E_f)^T,
where P^+ is the pseudo-inverse. Stop a row when the correlation between X_f and X_{f-2}
exceeds 99.9999% (f-2 because of period-2 oscillations) or after m = 1000 iterations;
converged rows are removed from the iteration.

Variants: GGS 1 (n = 1), GGS 2 (n = 2), GGS 2-1 (first n = 2, then n = 1). The exponent
works like "heating" in simulated annealing and helps escape local optima.
gamma = L/N controls the number of measurements: GGS 1 needs ~7N masks; GGS 2-1 works
from gamma = 4 and reaches ~98-99% of the theoretical focusing enhancement in noiseless
simulations; GGS 2 ~87%; GGS 1 at gamma = 4 often gets trapped (~14%). Each row of T is
retrieved only up to a global phase factor.
