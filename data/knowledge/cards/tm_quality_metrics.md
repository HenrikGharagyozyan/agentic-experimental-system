---
id: tm_quality_metrics
title: Measuring transmission-matrix accuracy invariantly
source: "Huang et al., Photonics Research 9(1), 34 (2021), Sec. 3 (enhancement as accuracy measure) and Fig. 3d (correlation coefficient between correct and retrieved TM rows)"
tags: [transmission matrix, correlation, accuracy, calibration, metric]
---
Intensity-only retrieval determines every row of T only up to an unknown global phase
(card intensity_only_measurement), so an element-wise error is meaningless. Two
phase-invariant metrics:

1. Row correlation, when the true T is known (simulation only):
   |<x_hat, x>| / (|x_hat| |x|) per row, averaged over rows; 1 = perfect up to a phase.
   Huang et al. use the absolute value of the correlation coefficient between one row of
   the correct and of the retrieved TM (Fig. 3d).
2. Focusing enhancement relative to theory, eta / eta_theory (card focusing_enhancement),
   which works on real hardware too; Huang et al. use it as their main accuracy measure.

Note: Fig. 3d specifically shows binary-amplitude probing (DMD), where all methods stay
at a correlation of about 0.6 regardless of gamma; with phase-only probing (our case)
GGS 2-1 reaches near-perfect accuracy at gamma = 4 (Fig. 2).

The calibration is valid only for the medium state it was measured in: the TM is
sensitive to translations/rotations of the medium and to the input and detection
hardware; Delloye et al. report a stability time of ~120 min (within 10%) (Methods).
Changing the medium or the SLM macro-pixel grid requires a new calibration.
