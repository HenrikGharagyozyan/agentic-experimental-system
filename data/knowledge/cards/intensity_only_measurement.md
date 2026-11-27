---
id: intensity_only_measurement
title: The core problem - the camera measures only intensity, so T must be retrieved
source: "Huang et al., Photonics Research 9(1), 34 (2021), Sec. 1 (Introduction) and Sec. 2; Delloye et al. 2023 (arXiv:2309.10764), Methods (transmission matrix calculation)"
tags: [transmission matrix, phase retrieval, intensity, camera, calibration, reference-free]
---
Light passes the SLM (input field E_in, N controlled macro-pixels), the scattering medium
(complex transmission matrix T, M x N) and reaches the camera: E_out = T E_in. Optical
fields oscillate too fast for detectors, which record only the time-averaged intensity
I_m = |E_out,m|^2 (Huang, Sec. 1). The phase of E_out - and therefore T itself - is not
measured directly.

Two ways to obtain T:
1. Interferometric / holographic: add a known reference field and step its relative
   phase; T follows from how the intensity changes. Delloye et al. estimate T this way
   (Methods: "as in [50]" = Popoff et al., PRL 104, 100601 (2010)).
2. Reference-free phase retrieval: send L random phase-only masks P (L x N) and measure
   only the amplitudes |E| = sqrt(I) (L x M); retrieve T iteratively with the Generalized
   Gerchberg-Saxton algorithm (card ggs_transmission_matrix). GGS 2-1 needs L >= 4N
   masks (gamma = L/N >= 4) (Huang, Sec. 2-3).

Consequences for any experiment on this setup:
- Almost every task starts with a T calibration: focusing needs rows of T, the Ising
  couplings J are computed from T, and the phase bias that makes Ising ground states
  magnetized regions is computed from T.
- The Ising optimisation itself does NOT need T: it uses the measured target intensity
  directly as feedback (card ground_state_search).
- From intensities alone each row of T is known only up to a global phase factor (and an
  overall scale), so T quality must be measured with phase-invariant metrics (card
  tm_quality_metrics).
- The calibration is valid only for the medium state and SLM macro-pixel grid it was
  measured with.
- Camera limits matter: Huang's experiment used an 8-bit CCD with SNR around 25; for
  SNR < 10 all retrieval algorithms degrade (Huang, Fig. 3c).

Note: the statement about the per-row phase ambiguity is general physics of
intensity-only measurement; Huang et al. do not state it explicitly.
