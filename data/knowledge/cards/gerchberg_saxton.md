---
id: gerchberg_saxton
title: Gerchberg-Saxton phase retrieval and its Fresnel-domain variants
source: "Zhao & Chi, Modified Gerchberg-Saxton (G-S) Algorithm and Its Application, Entropy 22, 1354 (2020), Eqs. 1-4 and Sec. 3"
tags: [gerchberg-saxton, phase retrieval, hologram, slm mask, fresnel, spr, dpr, mpr]
---
Classical GS computes a phase-only mask that produces a target intensity: start from a
random phase, propagate (Fourier transform), replace the amplitude by the target
amplitude, propagate back, keep only the phase, repeat. Convergence is monitored with
the mean squared error or the correlation coefficient (CC) between the produced and the
target amplitude; GS converges fast at first and then stagnates (approximate solution).

Zhao & Chi replace the Fourier transform by a Fresnel transform over distance z:
- SPR (single-phase retrieval): one phase mask; converges better than GS but still
  approximate (CC ~0.999 after 200 iterations);
- DPR / MPR (double / multiple-phase retrieval): 2..n cascaded phase masks in different
  planes; they reach an exact solution (CC = 1), used for multiple-image encryption.
The same GS loop works through a known transmission matrix (forward T, backward T^+) to
shape patterns (e.g. several foci) behind a scattering medium.
