### Preliminary Results

Our pilot shows that FedVerify improves training speed and final accuracy over the tested defenses on heterogeneous edge devices (Table 4). We evaluated the protocol on a 100-node testbed with 20% Byzantine clients that submitted poisoning updates. Clients held different data distributions, using a non-independent and identically distributed (non-IID) partition with Dirichlet parameter α = 0.2. Under these conditions, undefended FedAvg failed to reach 80% accuracy and finished at 34.2%.

FedVerify halved the wall-clock time to 80% accuracy relative to FL-Trust, the faster competing defense, while requiring approximately 45% fewer communication rounds. It reached the target in 5.6 hours and achieved a final accuracy 2.3 percentage points above FL-Trust. Relative to Krum, FedVerify reduced time to the target by approximately 62% and improved final accuracy by 4.4 percentage points. These comparisons show faster training alongside higher final accuracy in the pilot setting.

FedVerify incurred a per-round communication cost approximately 14% above FedAvg and Krum, while using approximately 23% less communication per round than FL-Trust. The additional per-round traffic accompanied fewer rounds to the target accuracy, a favorable tradeoff for the tested edge deployment (Table 4).
