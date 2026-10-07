### Preliminary Results

We ran a pilot of FedVerify on a testbed of 100 heterogeneous edge devices. With 20% of clients sending poisoned updates, FedVerify reached 80% accuracy in half the wall-clock time of FL-Trust, the strongest baseline, and finished with the highest final accuracy (Table 4).

Two conditions in the pilot made robust aggregation hard. Twenty of the 100 clients were Byzantine, meaning they sent poisoned model updates intended to degrade the global model. Client data were non-IID (not independent and identically distributed) under a Dirichlet partition with α = 0.2, so most clients held samples from only a few classes. Under this skew, honest updates already differed widely from one another, so a poisoned update was harder to single out.

We compared FedVerify with three aggregation rules. FedAvg (McMahan et al., 2017) averages all client updates and has no defense. Krum (Blanchard et al., 2017) keeps the single update closest to its nearest neighbors and discards the rest. FL-Trust (Cao et al., 2021) weights each update by its directional agreement with a reference update that the server computes on a small clean dataset.

Poisoning broke undefended training: FedAvg never reached 80% accuracy and ended at 34.2%. Krum, FL-Trust, and FedVerify all passed 80%. FedVerify finished highest, at 85.4%, which is 2.3 points above FL-Trust and 4.4 points above Krum.

The wall-clock advantage came from needing fewer rounds. To reach 80% accuracy, FedVerify needed 45% fewer rounds than FL-Trust and 66% fewer than Krum. Its per-round cost sat between the two robust baselines: dividing wall-clock time by rounds gives 2.9 minutes per FedVerify round, against 2.6 for Krum and 3.2 for FL-Trust. FedVerify spent about 12% more time per round than Krum and recovered that overhead by converging in a third as many rounds.

Per round, FedVerify transferred 1.7 MB (14%) more than FedAvg and Krum and 4.1 MB (23%) less than FL-Trust. Multiplying rounds by per-round communication gives each method's cumulative communication to reach 80% accuracy: 1.6 GB for FedVerify, 3.8 GB for FL-Trust, and 4.2 GB for Krum. FedVerify thus moved less than half the data of either robust baseline. On metered or low-bandwidth edge links, this total matters more than per-round size.
