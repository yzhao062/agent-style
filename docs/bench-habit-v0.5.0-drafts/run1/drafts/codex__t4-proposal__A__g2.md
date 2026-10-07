### Preliminary Results

Our pilot provides preliminary evidence that FedVerify improves training speed and final accuracy under poisoning attacks on heterogeneous edge devices. We evaluated the protocol on a 100-node testbed with 20% Byzantine clients conducting poisoning attacks. Client data followed different distributions (non-IID), using a Dirichlet partition with α = 0.2.

As Table 4 shows, FedVerify reached 80% accuracy in 115 rounds and 5.6 hours, compared with 210 rounds and 11.2 hours for FL-Trust. These measurements represent 45.2% fewer rounds and a 50% reduction in wall-clock time. Krum required 340 rounds and 14.8 hours to reach the same threshold. FedVerify achieved 85.4% final accuracy, exceeding FL-Trust by 2.3 percentage points and Krum by 4.4 percentage points. Undefended FedAvg finished at 34.2% and never reached 80% accuracy during the pilot.

FedVerify required 14.1 MB of communication per round, 13.7% more than FedAvg and Krum, and 22.5% less than FL-Trust. In this configuration, the additional communication relative to Krum accompanied faster training and higher final accuracy. The pilot supports FedVerify’s feasibility under the tested conditions. Further evaluation should quantify variability across repeated trials and test robustness across poisoning strategies and client data distributions.
