---
id: replica_overlap
title: Replica overlap and coupled spin clusters (two foci)
source: "Delloye et al. 2023 (arXiv:2309.10764), Fig. 3-4 and definition of q_alpha_beta"
tags: [replica, overlap, parisi, replica symmetry breaking, two foci, clusters, thin diffuser]
---
Optimising the summed intensity of two camera pixels creates two regions of magnetized
spins. Their extent is set by the interaction length; when the regions overlap, the
spins in the overlap contribute to both foci and couple the two clusters.

Replicas alpha, beta are ground states found from different random starts. Their
correlation is measured, in analogy with the Parisi order parameter, by an overlap q
computed in a zone of interest (spins that actually couple to the targets). We use the
standard q = (1/N) sum_i sigma_i^alpha sigma_i^beta and its absolute value |q| (global flip
symmetry).

Uncoupled regions are magnetized independently: their relative orientation agrees only
~50% of the time, so the mean |q| stays well below 1. Increasing the overlap (stronger
interaction) correlates the regions and |q| approaches 1 - replica-to-replica
fluctuations vanish, in analogy with the replica symmetry breaking transition.
