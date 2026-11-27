---
id: coupling_matrix_from_tm
title: Spin couplings J from the transmission matrix; thick vs thin scattering media
source: "Delloye et al. 2023 (arXiv:2309.10764), Eq. 1, Fig. 1-2 and Methods; phase-bias technique: Jacucci et al., PRA 105, 033502 (2022) (Delloye ref. [14], not in data/papers)"
tags: [ising, coupling, transmission matrix, thick medium, thin diffuser, interaction length, bias]
---
Expanding I = sum_{m in S} |sum_i t_mi sigma_i|^2 gives the couplings
J_ij = Re sum_{m in S} t_mi * conj(t_mj)   (real, symmetric), with H = - sum J sigma sigma.

Discrepancy: the paper prints J_ij = - sum_m Re(t_im t_jm) next to H = - sum J_ij sigma_i
sigma_j = - I (Eq. 1; in the PDF text a complex-conjugate bar may also be lost). With the
minus sign the two equalities contradict each other. We use the self-consistent form
above (positive sign, complex conjugate, indices t_mi = mode m, pixel i); a unit test
checks that H computed through J equals minus the optically computed intensity.

Thick scattering medium (fully developed speckle): couplings are all-to-all, with
Gaussian-distributed J as in the Sherrington-Kirkpatrick model (Delloye, text after
Eq. 1). In simulations this corresponds to i.i.d. circular Gaussian entries of T (the UTC
model; Huang et al. 2021, Sec. 3).

Thin diffuser: light reaching a camera pixel comes only from SLM pixels inside a cone
(Delloye, Fig. 1 inset, Fig. 2). The further the camera is from the diffuser, the wider
the cone, so the interaction length grows with distance. Two limits: fully developed
speckle (all-to-all couplings) and so short a distance that each output mode sees a
single macro-pixel (N decoupled spins) (Delloye, discussion of Fig. 2).

Phase bias: knowing T, a phase pattern ("bias") is encoded on the SLM together with the
spins so that the ground states become magnetized (uniform) regions (Delloye, Fig. 2
discussion and Methods: "the spins and bias (from the TM [14]) are encoded by the SLM").
Note: the exact bias formula is in Jacucci et al. [14], which is not in data/papers; our
implementation uses phi_bias,i = -Arg(sum_{m in S} t_mi), to be confirmed by a physicist.
