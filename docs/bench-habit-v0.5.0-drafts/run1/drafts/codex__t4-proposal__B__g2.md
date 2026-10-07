### Preliminary Results

Our pilot shows that FedVerify combines faster training with higher final accuracy under client poisoning and heterogeneous data (Table 4). We evaluated the protocol on a 100-node heterogeneous edge testbed with 20% Byzantine clients conducting poisoning attacks. Client data followed different distributions (non-IID), with Dirichlet α = 0.2. Under these conditions, undefended FedAvg failed to reach 80% accuracy.

FedVerify reached the 80% accuracy target in 5.6 hours, halving wall-clock time relative to FL-Trust, the faster of the two comparison defenses. It required approximately 45% fewer training rounds than FL-Trust and achieved a final accuracy of 85.4%, an improvement of 2.3 percentage points. Relative to Krum, FedVerify reduced wall-clock time to the target by approximately 62%.

The communication tradeoff favors FedVerify over FL-Trust: per-round traffic fell by approximately 23%, while exceeding undefended FedAvg by approximately 14%. Accounting for both rounds and per-round traffic, FedVerify required approximately 58% less communication than FL-Trust to reach the target accuracy. This reduction directly addresses the communication cost of robust training on edge devices.
