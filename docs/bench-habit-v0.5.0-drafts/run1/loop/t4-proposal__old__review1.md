1. **Soundness and sentence length:** The 33-word sentence beginning “Averaged over the rounds” overstates the explanation for the speedup. FedVerify also has shorter average rounds than FL-Trust, but longer rounds than Krum.

   **Suggested rewrite:** “Average round times were 2.6 minutes for Krum, 2.9 for FedVerify, and 3.2 for FL-Trust. FedVerify reached the threshold in fewer rounds than both baselines. Relative to FL-Trust, shorter average rounds also contributed to the wall-clock reduction.”

2. **Reproducibility:** The passage omits the dataset, model, poisoning strategy, hardware configuration, client participation schedule, optimization settings, and evaluation procedure. These omissions prevent readers from reproducing or assessing the comparison.

   **Suggested rewrite:** “The pilot used [dataset] and [model] on [hardware configuration]. Byzantine clients applied [poisoning strategy]. All methods used [participation schedule], [optimization settings], and [evaluation procedure], with method-specific settings documented in [location].”

3. **Soundness of final-accuracy comparisons:** The reported accuracy differences match Table 4, but the stopping budgets are unspecified. Readers cannot determine whether the methods received comparable training opportunities.

   **Suggested rewrite:** “At the reported endpoints, FedVerify achieved 85.4% accuracy, versus 83.1% for FL-Trust and 81.0% for Krum. These endpoints correspond to [state each method’s stopping criterion and training budget].”

4. **Uncalibrated claim:** “A small alpha concentrates each client’s data on a few classes” presents a probabilistic tendency as a guarantee for every client.

   **Suggested rewrite:** “A small alpha tends to produce more skewed client label distributions.”

5. **Sentence length:** The baseline sentence exceeds 30 words and combines method descriptions with three citations.

   **Suggested rewrite:** “Baselines included undefended FedAvg (McMahan et al. 2017), Krum (Blanchard et al. 2017), and FL-Trust (Cao et al. 2021). FedAvg averages client updates without a defense. Krum and FL-Trust provide Byzantine-robust comparisons.”

6. **Communication accounting and sentence length:** The 32-word cumulative-volume sentence gives correct estimates, but assumes constant communication per round. The passage also leaves the communication scope undefined.

   **Suggested rewrite:** “Communication measures [specify client or system scope and included traffic]. Multiplying per-round communication by rounds to threshold gives estimated totals of 1.62 GB for FedVerify, 3.82 GB for FL-Trust, and 4.22 GB for Krum. These estimates assume constant communication per round and use decimal gigabytes.”
