### Preliminary Results

We ran a pilot study to compare FedVerify with existing Byzantine-robust aggregation rules on heterogeneous edge hardware. The testbed has 100 edge nodes, 20 of which (20%) are Byzantine clients that send poisoned model updates. Client data are non-IID, with label distributions drawn from a Dirichlet distribution at α = 0.2; smaller α gives each client a more skewed label mix. The baselines are FedAvg with no defense (McMahan et al. 2017), Krum (Blanchard et al. 2017), and FL-Trust (Cao et al. 2021). Krum keeps the single client update whose distances to its nearest neighbors are smallest. FL-Trust weights each client update by its cosine similarity to an update that the server computes on a small clean dataset.

**Table 4.** Pilot results on the 100-node edge testbed with 20% Byzantine clients and Dirichlet α = 0.2.

| Method | Rounds to 80% accuracy | Wall-clock to 80% | Final accuracy | Communication per round |
|---|---|---|---|---|
| FedAvg (no defense) | never | n/a | 34.2% | 12.4 MB |
| Krum | 340 | 14.8 h | 81.0% | 12.4 MB |
| FL-Trust | 210 | 11.2 h | 83.1% | 18.2 MB |
| FedVerify | 115 | 5.6 h | 85.4% | 14.1 MB |

As Table 4 shows, FedVerify reaches 80% accuracy in 115 rounds and 5.6 hours of wall-clock time. It cuts rounds to 80% by 66% and wall-clock time by 62% relative to Krum, and by 45% and 50% relative to FL-Trust. FedAvg never reaches 80% and ends at 34.2%, so 20% Byzantine clients are enough to break undefended training in this setting. FedVerify finishes at 85.4%, which is 4.4 points above Krum (81.0%), 2.3 points above FL-Trust (83.1%), and 51.2 points above FedAvg.

Dividing wall-clock time by rounds gives 2.9 minutes per round for FedVerify, between Krum (2.6 minutes) and FL-Trust (3.2 minutes). The wall-clock gain therefore comes from needing fewer rounds. FedVerify sends 14.1 MB per round, which is 1.7 MB (14%) more than FedAvg and Krum (12.4 MB each) and 4.1 MB (23%) less than FL-Trust (18.2 MB). Multiplying rounds by per-round communication gives the total traffic to reach 80% accuracy: about 1.6 GB for FedVerify, 4.2 GB for Krum, and 3.8 GB for FL-Trust.

The pilot covers one Byzantine fraction (20%), one heterogeneity level (α = 0.2), and one 100-node testbed. It does not yet show how FedVerify behaves at other Byzantine fractions, under other attack types, or at larger scale. [Before submission, add the dataset, model, number of seeds, and standard deviation across seeds.]
