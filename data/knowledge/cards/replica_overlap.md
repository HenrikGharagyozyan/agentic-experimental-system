---
id: replica_overlap
title: Replica overlap and coupled spin clusters (two foci)
source: "Delloye et al. 2023 (arXiv:2309.10764), Fig. 3, Fig. 4 and the definition of q_alpha_beta in the text"
tags: [replica, overlap, parisi, replica symmetry breaking, two foci, clusters, thin diffuser]
---
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
