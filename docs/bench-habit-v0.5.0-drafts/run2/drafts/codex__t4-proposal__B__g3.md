### Preliminary Results

Our pilot evaluates FedVerify’s accuracy, training time, and communication cost under client poisoning on heterogeneous edge devices. We ran the protocol on a 100-node testbed with 20% Byzantine clients submitting poisoned updates. Client data followed different distributions (non-IID), using a Dirichlet partition with alpha = 0.2.

FedVerify reaches 80% accuracy in half the wall-clock time of FL-Trust, the faster comparison defense, using approximately 45% fewer rounds (Table 4). Its final accuracy exceeds FL-Trust by 2.3 percentage points. Krum also reaches the accuracy target but requires substantially longer training. Undefended FedAvg fails to reach the target, showing the need for protection under this pilot’s poisoning conditions.

The training-time improvement carries a communication tradeoff. FedVerify uses approximately 14% more communication per round than FedAvg and Krum, but 23% less than FL-Trust (Table 4). Its lower round count also reduces cumulative communication to the accuracy target relative to both comparison defenses. These measurements provide initial evidence that FedVerify can combine poisoning resistance with shorter training times on heterogeneous edge devices.
