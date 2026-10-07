### Preliminary Results

Our pilot evaluated FedVerify’s accuracy, training time, and communication cost under client poisoning on heterogeneous edge devices. We used a 100-node testbed with 20% Byzantine clients submitting poisoned updates. Client data followed a non-independent and identically distributed (non-IID) partition with Dirichlet α = 0.2, creating substantial differences in data distributions across clients.

Under these conditions, FedVerify reached 80% accuracy in 5.6 hours, halving FL-Trust’s wall-clock time and requiring approximately 45% fewer training rounds (Table 4). FedVerify also achieved the highest observed final accuracy, 85.4%, exceeding FL-Trust by 2.3 percentage points. Undefended FedAvg failed to reach the target and finished at 34.2% accuracy.

FedVerify’s faster training came with a communication tradeoff: each round transmitted approximately 14% more data than FedAvg or Krum. Compared with FL-Trust, FedVerify reduced communication per round by approximately 23%. The pilot therefore shows that FedVerify can combine accurate learning under poisoning with shorter training time and lower communication per round than FL-Trust.
