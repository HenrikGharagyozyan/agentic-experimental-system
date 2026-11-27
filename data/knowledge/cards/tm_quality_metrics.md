---
id: tm_quality_metrics
title: Measuring transmission-matrix accuracy invariantly
source: "Huang et al., Photonics Research 9(1), 34 (2021), Fig. 3d (correlation coefficient)"
tags: [transmission matrix, correlation, accuracy, calibration, metric]
---
Phase retrieval determines every row of T only up to an unknown global phase, so an
element-wise error is meaningless. Two invariant metrics:
1. In simulation (true T known): row correlation |<x_hat, x>| / (|x_hat| |x|), averaged
   over rows; 1 = perfect up to phase.
2. Universally (also on hardware): the focusing enhancement relative to theory,
   eta / eta_theory, obtained with phase-conjugate masks built from the retrieved rows.
The calibration is valid only for the medium state it was measured in: changing the
scattering medium (e.g. its drive voltage) or the SLM macro-pixel grid requires a new
calibration.
