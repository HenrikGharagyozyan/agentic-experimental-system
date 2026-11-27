---
id: ising_energy_from_intensity
title: Optical Ising machine - energy is minus the target intensity
source: "Delloye et al., An optical Ising spin glass simulator with tuneable short range couplings (arXiv:2309.10764, 2023), Eq. 1; Pierangeli et al., PRL 122, 213902 (2019)"
tags: [ising, spatial photonic ising machine, energy, intensity, spins, slm]
---
Spins sigma_i = +1/-1 are encoded as binary phases on the SLM macro-pixels: +1 -> phase 0,
-1 -> phase pi, i.e. the input field is E_in,i = exp(i phi_i) = sigma_i.
Light propagates through a scattering medium with transmission matrix T (M x N):
E_out = T E_in, and the camera measures I_m = |E_out,m|^2.

For a set S of target camera modes, the Ising Hamiltonian is realised optically:
H(sigma) = - sum_{m in S} I_m = - sum_{i,j} J_ij sigma_i sigma_j.

Minimising H = maximising the detected intensity at the target modes. Each camera frame
therefore measures the energy of the whole spin configuration in parallel, which is the
advantage of the optical simulator. H is invariant under a global flip sigma -> -sigma,
so every ground state is (at least) doubly degenerate.

One target mode gives a rank-one (Mattis-like) coupling matrix and a "ferromagnetic"
ground state up to the gauge of the phases of t_mi; two target modes give two regions of
spins whose overlap couples them.
