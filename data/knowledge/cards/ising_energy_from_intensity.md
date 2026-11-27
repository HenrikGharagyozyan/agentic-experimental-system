---
id: ising_energy_from_intensity
title: Optical Ising machine - energy is minus the target intensity
source: "Delloye et al., An optical Ising spin glass simulator with tuneable short range couplings (arXiv:2309.10764, 2023), Eq. 1 and introduction; original scheme: Pierangeli et al., PRL 122, 213902 (2019) (Delloye ref. [15], not in data/papers)"
tags: [ising, spatial photonic ising machine, energy, intensity, spins, slm]
---
Spins sigma_i = +1/-1 are encoded as binary phases of the SLM macro-pixels: +1 -> phase 0,
-1 -> phase pi (Delloye, text after Eq. 1), i.e. the input field is
E_in,i = exp(i phi_i) = sigma_i. Light propagates through the scattering medium:
E_out = T E_in, and the camera measures I_m = |E_out,m|^2.

For a set S of target camera modes the Ising Hamiltonian is realised optically
(Delloye, Eq. 1): H(sigma) = - sum_{i,j} J_ij sigma_i sigma_j = - I, where I is the
detected intensity, here I = sum_{m in S} I_m.

Minimising H = maximising the detected intensity at the target modes. Every camera frame
measures the energy of the whole configuration at once ("parallel measurements of the
energy"; Delloye, Methods). H is invariant under the global flip sigma -> -sigma (the
field changes sign, the intensity does not), so ground states are at least doubly
degenerate.

Note (derived here, not stated in the paper): for one target mode with transmission row
t, J_ij = Re(t_i conj(t_j)) = Re(t_i)Re(t_j) + Im(t_i)Im(t_j), a coupling matrix of rank
<= 2. Without a phase bias its ground state follows the signs of the (random) phases of
t, not a uniform magnetization; with the phase bias computed from T (card
coupling_matrix_from_tm) the ground state becomes a magnetized region. Two target modes
give two regions whose overlap couples them (card replica_overlap).
