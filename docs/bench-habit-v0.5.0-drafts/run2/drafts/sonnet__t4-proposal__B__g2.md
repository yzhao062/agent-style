### Preliminary Results

We ran a pilot of FedVerify on a 100-node heterogeneous edge testbed. Byzantine clients made up 20% of the clients (20 of the 100 nodes) and sent poisoned model updates intended to degrade the global model. The data is non-IID (distributed differently across clients): a Dirichlet split with alpha = 0.2 gives each client a skewed share of the classes. We compared FedVerify with three baselines. FedAvg (McMahan et al. 2017) averages client updates with no defense. Krum (Blanchard et al. 2017) keeps the single client update closest to its neighbors. FL-Trust (Cao et al. 2021) weights each update by its similarity to one that the server computes on a small trusted dataset.

Table 4 reports rounds and wall-clock time to reach 80% accuracy, final accuracy, and communication per round. Without a defense, FedAvg never reaches 80% and ends at 34.2%, so the poisoning attack is effective on this testbed. FedVerify reaches 80% in 115 rounds, which is 66% fewer than Krum (340) and 45% fewer than FL-Trust (210). In wall-clock time it takes 5.6 hours, a 2.6 times speedup over Krum (14.8 h) and a 2.0 times speedup over FL-Trust (11.2 h). Average round time, computed from Table 4, is similar across the three defenses: 157 s for Krum, 175 s for FedVerify, and 192 s for FL-Trust. The wall-clock savings therefore follow from the smaller round count.

FedVerify ends at 85.4% accuracy, 2.3 points above FL-Trust and 4.4 points above Krum. Table 4 reports no confidence intervals, so we read these final-accuracy gaps as suggestive.

Per round, FedVerify sends 14.1 MB. That is 1.7 MB (14%) above FedAvg and Krum (12.4 MB each) and 4.1 MB (23%) below FL-Trust (18.2 MB). Multiplying per-round volume by rounds to 80% accuracy gives cumulative communication 2.6 times lower than Krum and 2.4 times lower than FL-Trust.

**References:** Blanchard et al. 2017 (Krum, NeurIPS); Cao et al. 2021 (FLTrust, NDSS); McMahan et al. 2017 (FedAvg, AISTATS).
