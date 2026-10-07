### Preliminary Results

The pilot tests whether FedVerify keeps federated training accurate and fast when one in five edge devices is malicious and client data are highly skewed. Table 4 compares FedVerify with three baselines on rounds and wall-clock time to reach 80% accuracy, final accuracy, and communication per round.

We ran all four methods on a 100-node heterogeneous edge testbed, with each node acting as one federated client. Twenty clients (20%) are Byzantine: they send poisoned model updates intended to corrupt the shared model. [TODO: dataset, model, poisoning attack, and number of runs.] To make client data non-IID (not independent and identically distributed), we split the training data across clients using a Dirichlet distribution with concentration α = 0.2. Smaller α produces stronger skew; at α = 0.2, most clients hold data concentrated on a few labels. Strong skew makes defense harder, because honest clients then also send updates that differ from the majority.

The baselines cover no defense, a distance-based defense, and a trust-based defense. FedAvg (McMahan et al., 2017) averages all client updates without filtering. Krum (Blanchard et al., 2017) keeps only the single update with the smallest total distance to its nearest neighbors. FL-Trust (Cao et al., 2021) has the server compute its own update on a small, clean root dataset. It then weights each client update by its cosine similarity to that server update.

The attack breaks undefended training: FedAvg never reaches 80% accuracy and finishes at 34.2%. All three defenses reach 80%, but at different speeds. FedVerify needs 115 rounds, 45% fewer than FL-Trust (210) and 66% fewer than Krum (340). In wall-clock time, it reaches 80% in 5.6 hours, a 2.0× speedup over FL-Trust (11.2 hours) and 2.6× over Krum (14.8 hours).

Most of this speedup comes from needing fewer rounds. Dividing wall-clock time by rounds gives 2.9 minutes per round for FedVerify, 3.2 for FL-Trust, and 2.6 for Krum. Per round, FedVerify takes 12% longer than Krum, but it needs 225 fewer rounds.

Final accuracy follows the same ranking. FedVerify ends at 85.4%, which is 2.3 points above FL-Trust (83.1%) and 4.4 points above Krum (81.0%). Krum finishes only 1.0 point past the 80% threshold.

FedVerify's defense adds communication. Each round moves 14.1 MB, 14% more than the 12.4 MB of FedAvg and Krum but 23% less than FL-Trust's 18.2 MB. Because FedVerify needs fewer rounds, its total communication to reach 80% accuracy (rounds × communication per round) is the lowest of the three defenses. FedVerify moves about 1.6 GB, compared with 3.8 GB for FL-Trust and 4.2 GB for Krum. These reductions of 58% and 62% matter on edge devices with slow or metered uplinks.

The pilot fixes the Byzantine fraction at 20% and the skew at α = 0.2, on one testbed. It remains open whether FedVerify keeps its advantage with more attackers or at other levels of skew.
