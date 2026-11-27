---
id: ground_state_search
title: Ground-state search by intensity feedback (batch spin flips)
source: "Delloye et al. 2023 (arXiv:2309.10764), Methods: 'Transmission matrix calculation and ground-state search' and 'Numerical methods'"
tags: [ising, optimization, ground state, batch flip, feedback, iterations, plateau]
---
Experiment (Delloye, Methods): start from a random configuration of N binary macro-pixels
(spins). At each iteration a random batch of spins is flipped, and the flip is kept if
it increases the intensity at the chosen output mode. The batch size decreases during
the optimisation, from 12% of the pixels down to a single pixel for the last ~600
iterations.

Numerical model (Delloye, Methods): constant-amplitude input with random binary phases,
Gaussian i.i.d. T; at each iteration a single randomly selected spin is flipped and kept
if the output intensity increased. With a noiseless detector ~10N iterations are
sufficient for good convergence, i.e. until the focus intensity reaches a plateau.

The setup is algorithm-agnostic: "any algorithm can be used", because the advantage lies
in the parallel optical measurement of the energy (Delloye, Methods). Too few iterations
leave the system far from the ground state; replicas (independent runs from different
random starts) show whether different runs end in the same state.

Note: the simulated-annealing (Metropolis) alternative available in our system is our
addition; Delloye et al. only use the greedy batch-flip feedback.
