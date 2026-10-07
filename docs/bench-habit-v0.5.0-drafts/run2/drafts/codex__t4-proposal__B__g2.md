### Preliminary Results

Our pilot shows that FedVerify accelerates training under poisoning attacks and heterogeneous client data, with a measurable communication tradeoff (Table 4). We evaluated the protocol on a 100-node heterogeneous edge testbed with 20% Byzantine clients conducting poisoning attacks. Clients held non-independent and identically distributed (non-IID) data, with Dirichlet parameter α = 0.2 controlling the distribution across clients. Under these conditions, undefended FedAvg failed to reach 80% accuracy and finished at 34.2%.

FedVerify reached 80% accuracy in 5.6 hours, halving wall-clock time relative to FL-Trust, the faster defense baseline. It required 45% fewer training rounds than FL-Trust and achieved a final accuracy 2.3 percentage points higher. Relative to Krum, FedVerify reduced wall-clock time to the target by 62%. Its final accuracy of 85.4% was the highest among the tested methods.

The communication cost depends on the comparator: FedVerify used 14% more data per round than Krum and 23% less than FL-Trust. In this pilot, the additional per-round traffic over Krum accompanied fewer training rounds and a shorter time to the accuracy target.
