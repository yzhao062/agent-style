1. **Soundness: the timing explanation overstates the evidence.** “Per-round time is similar … so the speedup comes from FedVerify needing fewer rounds” treats unequal averages as equivalent and exceeds 30 words. FedVerify’s average round takes longer than Krum’s and less time than FL-Trust’s.
   
   Suggested rewrite: “FedVerify’s lower round count drives its shorter time to target. Against Krum, this reduction outweighs a higher average time per round.”

2. **Undersell: “indicates feasibility” obscures the supported comparative result.** Missing confidence intervals limits certainty about repeatability, but the reported pilot shows advantages in time to target and final accuracy.
   
   Suggested rewrite: “Under the evaluated poisoning and non-IID conditions, FedVerify reached the accuracy target faster and achieved higher final accuracy than both robust baselines. Run-to-run uncertainty remains unquantified.”

3. **Clarity: several sentences transcribe Table 4.** “FedVerify reached …,” “FL-Trust needed …,” “FedVerify also ended …,” “FedVerify sends …,” and “That is …” repeat individual entries. State the comparative patterns and retain the communication tradeoff.
   
   Suggested rewrite: “FedVerify halved time to target relative to FL-Trust, the faster robust baseline, while achieving the highest final accuracy. Its per-round communication fell between the robust baselines: above Krum and below FL-Trust.”

4. **Soundness and writing: cumulative communication needs an explicit estimation assumption.** “Because FedVerify needs fewer rounds …” exceeds 30 words. Multiplication estimates cumulative traffic only if the reported per-round volume represents rounds through the target.
   
   Suggested rewrite: “Using Table 4’s per-round volumes, estimated communication to target is about 58% lower than FL-Trust’s and 62% lower than Krum’s. These estimates assume representative per-round traffic.”

5. **Claim scope: “never reached” lacks a training horizon.** The table supports failure to reach the target during evaluation, not failure indefinitely. Final-accuracy comparisons also require a stated stopping rule.
   
   Suggested rewrite: “FedAvg did not reach 80% accuracy within the evaluated training horizon. Final accuracies were measured at [state the stopping rule for each method].”

6. **Reproducibility: important experimental details are missing.** The passage does not identify the dataset, model, hardware distribution, attack configuration, training settings, or measurement boundaries. FL-Trust also requires a trusted root dataset whose construction affects the comparison. ([Original FLTrust paper](https://arxiv.org/abs/2012.13995))
   
   Suggested rewrite: “The pilot used [dataset and model], [hardware and network configuration], and [poisoning attacks and adversary capabilities]. Training and baseline tuning followed [protocol reference]. FL-Trust used [root dataset source, size, and distribution]. Accuracy, timing, and communication followed [evaluation and accounting definitions].”

7. **Unsupported procedural specificity: the task data do not establish label partitioning.** “Simulated with a Dirichlet label partition” adds an implementation detail beyond the supplied Dirichlet concentration. The citation does not establish which procedure this pilot used.
   
   Suggested rewrite: “Client data were non-IID, using a Dirichlet partition with concentration alpha = 0.2.” Restore “label partition” once the implementation is confirmed.

8. **Writing: the baseline-description sentence exceeds 30 words.** Its nested explanation and three citations obscure the comparison.
   
   Suggested rewrite: “We compared FedVerify with undefended FedAvg (McMahan et al. 2017). The robust baselines were Krum (Blanchard et al. 2017) and FL-Trust (Cao et al. 2021).”
