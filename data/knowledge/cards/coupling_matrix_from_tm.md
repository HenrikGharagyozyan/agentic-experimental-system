---
id: coupling_matrix_from_tm
title: Spin couplings J from the transmission matrix
source: "Delloye et al. 2023 (arXiv:2309.10764), Eq. 1 and Fig. 1-2; Jacucci et al., PRA 105, 033502 (2022)"
tags: [ising, coupling, transmission matrix, thick medium, thin diffuser, interaction length]
---
Expanding I_m = |sum_i t_mi sigma_i|^2 gives the couplings
J_ij = Re sum_{m in S} t_mi * conj(t_mj)   (real and symmetric).

Note: the paper prints J_ij = -sum_m Re(t_im t_jm); with H = -sum J sigma sigma = -I the
self-consistent form is the one above (positive sign, complex conjugate).

Thick scattering medium (fully developed speckle): the entries of T are i.i.d. circular
Gaussian (UTC model) -> all-to-all couplings, Sherrington-Kirkpatrick-like system.

Thin diffuser / short propagation distance: light reaching camera mode m comes only from
SLM pixels inside a cone around it, so t_mi decays with the distance between pixel i and
mode m. The interaction length grows with the distance to the diffuser. Two limits:
fully developed speckle (all-to-all) and no mixing (N decoupled spins). Knowledge of T
also allows adding a phase bias so that ground states are magnetized regions.
