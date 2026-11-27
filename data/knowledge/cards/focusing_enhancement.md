---
id: focusing_enhancement
title: Focusing through a scattering medium and the enhancement factor
source: "Huang et al., Photonics Research 9(1), 34 (2021), Sec. 3 (definition and theory), Sec. 4 (experiments, multiple foci); Vellekoop & Mosk, Opt. Lett. 32, 2309 (2007) (Huang ref. [24], not in data/papers)"
tags: [focusing, enhancement, phase conjugation, transmission matrix quality, theory]
---
Sending the phase-conjugated field of one row of the retrieved TM forms a focus on that
camera mode (Huang, Sec. 3); for a phase-only SLM the mask is phi_i = -Arg(x_mi). The
quality of the focus - and thus of the retrieved TM - is quantified by the enhancement
eta = I_foc / I_avg, where I_avg is the ensemble-averaged speckle intensity for random
inputs.

Theory for (continuous) phase-only modulation (Huang, Sec. 3): eta = pi (N - 1) / 4 + 1,
N = number of independent controls (columns of the TM).

Multiple foci (Huang, Sec. 4): "the theoretical value of the enhancement should be
modified by inserting an additional N_f in the denominator", N_f = number of foci.
Note: the paper gives this only in words; we use eta_theory = pi (N - 1) / (4 N_f) + 1.

Note: this theoretical value does NOT apply to binary (0/pi) phase modulation, which gives
a lower enhancement; Huang et al. do not treat binary-phase focusing (Fig. 3d concerns
binary-AMPLITUDE probing with a DMD).

Experiments (Huang, Sec. 4-5): enhancements of 60-70% of the theory "can be routinely
achieved" (ground glass: 65.6% for 10 foci at N = 720; multimode fibre single focus:
76% with GGS 2-1). Losses come from SLM phase errors, laser intensity fluctuations,
camera noise and time variation of the medium.
Discrepancy (inside the paper): the caption of Fig. 6 lists GGS 1, GGS 2, GGS 2-1 with
82.4%, 71.5%, 4.1%, while the text reports 76% (GGS 2-1), 67% (GGS 2), 5% (GGS 1) for the
same experiment; the caption order appears reversed. Trust the text.
