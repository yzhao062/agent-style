### Preliminary Results

Our pilot provides preliminary evidence that FedVerify can sustain accurate, efficient federated learning under poisoning attacks on heterogeneous edge devices. We evaluated the protocol on a 100-node testbed with 20% Byzantine clients, malicious participants performing poisoning attacks. Client data followed different distributions across devices, a non-IID setting generated with Dirichlet α = 0.2.

As Table 4 shows, FedVerify reached 80% accuracy in 115 rounds and 5.6 hours. Compared with FL-Trust, this represents 45.2% fewer rounds and 50% less wall-clock time; compared with Krum, the reductions were 66.2% and 62.2%, respectively. FedVerify also achieved 85.4% final accuracy, exceeding FL-Trust by 2.3 percentage points and Krum by 4.4 percentage points. Undefended FedAvg finished at 34.2% and never reached the 80% target during the pilot.

FedVerify required 14.1 MB of communication per round, 13.7% more than FedAvg and Krum, but 22.5% less than FL-Trust. This measured tradeoff supports further investigation: FedVerify incurred additional communication relative to Krum while reaching the target accuracy sooner and achieving higher final accuracy.

These results support feasibility under the tested conditions. Table 4 alone establishes neither statistical significance nor robustness across other attacks and deployment conditions. The proposed evaluation will quantify variability through repeated trials and examine how attack type, Byzantine-client fraction, and data heterogeneity affect accuracy, training time, and communication.
