---
id: ground_state_search
title: Ground-state search by intensity feedback (batch spin flips)
source: "Delloye et al. 2023 (arXiv:2309.10764), Methods: transmission matrix calculation and ground-state search; numerical methods"
tags: [ising, optimization, ground state, batch flip, feedback, iterations, plateau]
---
Recurrent digital feedback: start from a random configuration of N binary macro-pixels.
At each iteration a random batch of spins is flipped; the flip is kept only if it
increases the intensity at the chosen output mode(s). The batch size decreases during
the optimisation, from about 12% of the pixels down to a single pixel for the last ~600
iterations. In numerical simulations with a noiseless detector ~10N iterations are
sufficient for good convergence, i.e. until the focus intensity reaches a plateau.

The setup is algorithm-agnostic: any optimiser (e.g. simulated annealing with a
Metropolis rule) can be used, because the advantage lies in the parallel optical
measurement of the energy. Too few iterations leave the system in a high-energy
configuration; replicas (independent runs from different random starts) reveal whether
the landscape has one or many competing minima.
