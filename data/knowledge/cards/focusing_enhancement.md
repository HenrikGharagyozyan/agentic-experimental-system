---
id: focusing_enhancement
title: Focusing through a scattering medium and the enhancement factor
source: "Huang et al., Photonics Research 9(1), 34 (2021), Sec. 3; Vellekoop & Mosk, Opt. Lett. 32, 2309 (2007)"
tags: [focusing, enhancement, phase conjugation, transmission matrix quality, theory]
---
With a retrieved row x_m of the transmission matrix, the phase-conjugate mask
phi_i = -Arg(x_mi) focuses light on camera mode m. The quality of the retrieved TM is
quantified by the enhancement eta = I_focus / <I>_random, where <I>_random is the
ensemble-averaged speckle intensity for random input masks.

For continuous phase-only modulation the theoretical enhancement is
eta_theory = pi (N - 1) / 4 + 1, N = number of independent SLM controls. For N_f
simultaneous foci an additional N_f enters the denominator: pi (N - 1) / (4 N_f) + 1.
This formula is NOT valid for binary (0/pi) modulation, which gives a lower enhancement.

The ratio eta / eta_theory is a universal TM-quality metric (it does not need the true
T). Experiments typically reach 60-80% of the theory because of SLM phase errors, laser
fluctuations, camera noise and drift of the medium; noise with SNR < 10 degrades all
retrieval algorithms.
