# Knowledge pack — на проверку физику

Этот документ — **дословный** вывод `uv run expsys knowledge`: ровно тот текст, который
LLM-агент Scientist получает в системном промпте как единственный источник научных
знаний (поиска по статьям нет). Агент цитирует карточки по `card_id`; числа он не
считает — все расчёты делает детерминированный код (`scientific_core`).

- Карточек: 9; размер: 17514 символов; sha256: `0840efd1e6fcc9a89bea52f8d93d10ad28a0900919aa5d0c8489641d9a298330`
- Источники: `data/knowledge/cards/*.md`; первоисточники — три статьи в `data/papers/`
  (Delloye et al. 2023; Huang et al. 2021; Zhao & Chi 2020).
- Перегенерировать: `uv run expsys knowledge` (тест `test_review_document_is_up_to_date`
  падает, если этот файл расходится с карточками).

**Что особенно просим проверить** (места, помеченные в тексте как *Discrepancy* / *Note*):

1. Знак и сопряжение в `J_ij = Re Σ_{m∈S} t_mi·conj(t_mj)` против напечатанного в Delloye,
   ур. 1 (`coupling_matrix_from_tm`).
2. Формула фазового bias `φ_bias,i = −Arg(Σ_{m∈S} t_mi)` — у Delloye только ссылка на
   Jacucci et al. 2022 [14], которой нет в `data/papers` (`coupling_matrix_from_tm`).
3. Определение overlap реплик: стандартный Паризи `|q|` против формулы Delloye
   (`replica_overlap`).
4. Теория enhancement для N_f фокусов: `π(N−1)/(4N_f) + 1` — у Huang дано словами
   (`focusing_enhancement`); неприменимость `π/4` к бинарной 0/π модуляции.
5. Прочтение DPR (Zhao & Chi, ур. 14): вторая маска — комплексное частное, не строго
   фазовая (`gerchberg_saxton`).
6. Утверждение о ранге ≤ 2 матрицы J для одной моды (`ising_energy_from_intensity`).

Ниже, после разделителя, — дословный текст пакета.

<!-- BEGIN VERBATIM KNOWLEDGE PACK -->
# Knowledge pack

The 9 knowledge cards below are your ONLY scientific references (human-curated summaries of the papers, with equation/section references). Cite the cards you rely on by their `card_id` in `citations`; never cite anything else. Lines marked 'Discrepancy' or 'Note' explain where our convention differs from the printed paper.

---

## Card `coupling_matrix_from_tm` — Spin couplings J from the transmission matrix; thick vs thin scattering media

Source: Delloye et al. 2023 (arXiv:2309.10764), Eq. 1, Fig. 1-2 and Methods; phase-bias technique: Jacucci et al., PRA 105, 033502 (2022) (Delloye ref. [14], not in data/papers)
Tags: ising, coupling, transmission matrix, thick medium, thin diffuser, interaction length, bias

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

---

## Card `focusing_enhancement` — Focusing through a scattering medium and the enhancement factor

Source: Huang et al., Photonics Research 9(1), 34 (2021), Sec. 3 (definition and theory), Sec. 4 (experiments, multiple foci); Vellekoop & Mosk, Opt. Lett. 32, 2309 (2007) (Huang ref. [24], not in data/papers)
Tags: focusing, enhancement, phase conjugation, transmission matrix quality, theory

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

---

## Card `gerchberg_saxton` — Gerchberg-Saxton phase retrieval and its Fresnel-domain variants (SPR, DPR, MPR)

Source: Zhao & Chi, Modified Gerchberg-Saxton (G-S) Algorithm and Its Application, Entropy 22, 1354 (2020): GS Eqs. 1-4 (Sec. 2.1), SPR Eqs. 7-10 (Sec. 3.1), CC Eq. 11, DPR Eqs. 12-21 (Sec. 3.2), MPR Eqs. 22-25 (Sec. 3.3), convergence Sec. 4
Tags: gerchberg-saxton, phase retrieval, hologram, slm mask, fresnel, spr, dpr, mpr

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

---

## Card `ggs_transmission_matrix` — Generalized Gerchberg-Saxton (GGS) retrieval of the transmission matrix

Source: Huang et al., Generalizing the Gerchberg-Saxton algorithm for retrieving complex optical transmission matrices, Photonics Research 9(1), 34 (2021), Eqs. 1-4, Sec. 2, Fig. 2
Tags: transmission matrix, calibration, phase retrieval, ggs, gerchberg-saxton, intensity only, gamma

Probe the medium with L random phase-only masks, grouped in the probing matrix P (L x N,
entries exp(i theta), theta uniform in [0, 2pi); Eq. 1). The target-plane field is
E = P X^T (Eq. 2), X being the unknown TM (M x N); the camera gives |E| (L x M).

Iteration f (Eqs. 3-4), with X~_f the estimate of X:
  E~_f = |E|^n (elementwise) * exp(i Arg(P X~_{f-1}^T)),
  X~_f = (P^+ E~_f)^T,   P^+ = pseudo-inverse of P.
Note: Eq. 3 is printed with |E|; the exponent n ("|E|^n is used to replace |E|") is
introduced in the text of Sec. 2.

Stopping (Sec. 2): a row stops when the correlation between X~_f and X~_{f-2} exceeds
99.9999% (f-2, not f-1, because of a period-2 oscillation), or after m iterations
(m = 1000 by default). Correlations are computed row by row and converged rows leave the
iteration. In GGS 2-1 at N = 1296 the two steps take ~287 and ~34 iterations (Sec. 5).

Variants (Sec. 2): GGS 1 (n = 1, the direct algorithm), GGS 2 (n = 2), GGS 2-1 (first
n = 2, then n = 1). The exponent acts like artificial "heat" in simulated annealing and
helps escape local optima. gamma = L/N: GGS 1 needs about 7N masks; GGS 2-1 works with 4N.

Numbers (noiseless UTC simulations): at N = 400, gamma = 4 the enhancement reaches 99.1%
(GGS 2-1), 87.1% (GGS 2) and 14.3% (GGS 1) of the theoretical value (Fig. 2a); the GGS 1
and GGS 2 curves cross near gamma = 6. At gamma = 4, GGS 2-1 gives 98.0-98.9% for
N = 64...1296 (Fig. 2c). GGS 1 at N = 1296: often trapped at gamma = 4; ~76% of runs near
theory at gamma = 6 and 95% at gamma = 7 (Fig. 2d).

---

## Card `ground_state_search` — Ground-state search by intensity feedback (batch spin flips)

Source: Delloye et al. 2023 (arXiv:2309.10764), Methods: 'Transmission matrix calculation and ground-state search' and 'Numerical methods'
Tags: ising, optimization, ground state, batch flip, feedback, iterations, plateau

Experiment (Delloye, Methods): start from a random configuration of N binary macro-pixels
(spins). At each iteration a random batch of spins is flipped, and the flip is kept if
it increases the intensity at the chosen output mode. The batch size decreases during
the optimisation, from 12% of the pixels down to a single pixel for the last ~600
iterations.

Numerical model (Delloye, Methods): constant-amplitude input with random binary phases,
Gaussian i.i.d. T; at each iteration a single randomly selected spin is flipped and kept
if the output intensity increased. With a noiseless detector ~10N iterations are
sufficient for good convergence, i.e. until the focus intensity reaches a plateau.

The setup is algorithm-agnostic: "any algorithm can be used", because the advantage lies
in the parallel optical measurement of the energy (Delloye, Methods). Too few iterations
leave the system far from the ground state; replicas (independent runs from different
random starts) show whether different runs end in the same state.

Note: the simulated-annealing (Metropolis) alternative available in our system is our
addition; Delloye et al. only use the greedy batch-flip feedback.

---

## Card `intensity_only_measurement` — The core problem - the camera measures only intensity, so T must be retrieved

Source: Huang et al., Photonics Research 9(1), 34 (2021), Sec. 1 (Introduction) and Sec. 2; Delloye et al. 2023 (arXiv:2309.10764), Methods (transmission matrix calculation)
Tags: transmission matrix, phase retrieval, intensity, camera, calibration, reference-free

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

---

## Card `ising_energy_from_intensity` — Optical Ising machine - energy is minus the target intensity

Source: Delloye et al., An optical Ising spin glass simulator with tuneable short range couplings (arXiv:2309.10764, 2023), Eq. 1 and introduction; original scheme: Pierangeli et al., PRL 122, 213902 (2019) (Delloye ref. [15], not in data/papers)
Tags: ising, spatial photonic ising machine, energy, intensity, spins, slm

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

---

## Card `replica_overlap` — Replica overlap and coupled spin clusters (two foci)

Source: Delloye et al. 2023 (arXiv:2309.10764), Fig. 3, Fig. 4 and the definition of q_alpha_beta in the text
Tags: replica, overlap, parisi, replica symmetry breaking, two foci, clusters, thin diffuser

Optimising the summed intensity of two camera pixels creates two regions of magnetized
spins (with the phase bias from T); their extent is set by the interaction length. Where
the regions overlap, the spins contribute to both foci and couple the two clusters. The
overlap can be tuned by the diffuser-camera distance or, at fixed distance, by moving the
two target pixels on the camera (Delloye, Fig. 3 and text).

Replicas alpha, beta are ground states found from different random starts. Their
correlation is evaluated in a zone of interest smaller than the full SLM mask (green
square in Fig. 4a). Delloye plots q_max = argmax_q P(q) of the distribution of q.

Discrepancy: the paper defines (as printed, for fully magnetized configurations)
q_alpha_beta = 1 - |sum_i (X_i^alpha - X_i^beta)| / N with X in {-1, 1}; the typeset
formula looks garbled. We use the standard Parisi overlap
q = (1/N) sum_i sigma_i^alpha sigma_i^beta in the zone of interest and compare |q|
(because of the global flip symmetry). Both measure how similar replica ground states
are, but their numerical values differ.

Physics (Delloye, Fig. 4 and text): uncoupled regions are magnetized independently, so
their relative orientation agrees only ~50% of the time; when the regions get closer and
overlap, their magnetizations become correlated and the replica correlation approaches
1 - replica-to-replica fluctuations vanish, in analogy with replica symmetry breaking.

---

## Card `tm_quality_metrics` — Measuring transmission-matrix accuracy invariantly

Source: Huang et al., Photonics Research 9(1), 34 (2021), Sec. 3 (enhancement as accuracy measure) and Fig. 3d (correlation coefficient between correct and retrieved TM rows)
Tags: transmission matrix, correlation, accuracy, calibration, metric

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
<!-- END VERBATIM KNOWLEDGE PACK -->
