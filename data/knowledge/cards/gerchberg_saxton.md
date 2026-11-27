---
id: gerchberg_saxton
title: Gerchberg-Saxton phase retrieval and its Fresnel-domain variants (SPR, DPR, MPR)
source: "Zhao & Chi, Modified Gerchberg-Saxton (G-S) Algorithm and Its Application, Entropy 22, 1354 (2020): GS Eqs. 1-4 (Sec. 2.1), SPR Eqs. 7-10 (Sec. 3.1), CC Eq. 11, DPR Eqs. 12-21 (Sec. 3.2), MPR Eqs. 22-25 (Sec. 3.3), convergence Sec. 4"
tags: [gerchberg-saxton, phase retrieval, hologram, slm mask, fresnel, spr, dpr, mpr]
---
Classical GS (Sec. 2.1, Eqs. 1-4): start from an initial guess, Fourier transform, replace
the amplitude by the known target amplitude F while keeping the phase, inverse transform,
impose the source-plane constraint, repeat. Convergence is controlled with the mean
squared error or the correlation coefficient CC = COV(f, f_hat) / (sigma_f sigma_f_hat)
(Eq. 11). In their example GS converges fast at first and stagnates after ~50 of 200
iterations: only an approximate solution is reached.

Fresnel-domain variants (Sec. 3), with FrT_z the Fresnel transform over distance z:
- SPR, single-phase retrieval (Eqs. 7-10): one phase mask exp(i phi), forward FrT_z1,
  replace the amplitude by the target image f, back-propagate FrT_{-z1}, keep the phase.
  Converges better than GS but still approximately (CC = 0.9988 after 200 iterations).
- DPR, double-phase retrieval (Eqs. 12-21): two masks in cascaded planes z1, z2; reaches
  CC = 1 after 15 iterations (exact recovery).
- MPR, multiple-phase retrieval (Eqs. 22-25): n cascaded masks; SPR and DPR are special
  cases. Applications in the paper: (multiple-)image encryption.
Sec. 4: GS and SPR are error-reduction (many-to-one) iterations, DPR/MPR rely on linear
operations, which is why they can reach the exact solution.

Note (our reading of Eq. 14): the second DPR mask is obtained as a complex quotient
FrT_{-z2}[f S/|S|] / FrT_z1[exp(i phi_1)] without normalising its modulus, so it is not
strictly phase-only; this extra freedom is what allows CC = 1. A physicist should confirm
before DPR/MPR is used with phase-only SLMs.

Note (our extension, not in the papers): the same GS loop works through a known
transmission matrix (forward T, backward T^+) to shape target patterns, e.g. several
foci, behind a scattering medium.
