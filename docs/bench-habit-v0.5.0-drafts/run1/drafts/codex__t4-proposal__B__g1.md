### Preliminary Results

Our pilot shows that FedVerify improves accuracy and reduces training time under poisoning attacks on heterogeneous edge devices (Table 4). We evaluated the protocol on a 100-node testbed with 20% Byzantine clients submitting poisoned updates. Client data followed different distributions, using a non-IID Dirichlet partition with α = 0.2.

Among the tested defenses, FedVerify reached 80% accuracy fastest and achieved the highest final accuracy. Compared with FL-Trust, it halved wall-clock time to the target and required 45% fewer training rounds. Final accuracy increased by 2.3 percentage points to 85.4%. Krum also reached the target, but required substantially more time; undefended FedAvg failed to reach it and finished at 34.2% accuracy.

FedVerify’s communication cost reflects a practical tradeoff for edge deployment. Per-round communication was approximately 14% higher than Krum and undefended FedAvg, but 23% lower than FL-Trust. In this pilot, the additional traffic relative to Krum accompanied a 62% reduction in wall-clock time to 80% accuracy.
