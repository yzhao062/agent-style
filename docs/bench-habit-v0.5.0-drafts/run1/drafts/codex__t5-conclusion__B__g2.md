## Conclusion

We presented AdaptRL, which transfers grasping policies from simulation to a real robot by learning residual dynamics online. These residuals capture differences between simulated and observed robot dynamics.

In real-robot evaluations with 100 trials per object category, AdaptRL achieves higher grasp success than both baselines across all five categories (Table 5). Mean success reaches 82.2%, exceeding DAgger by 19.2 percentage points and domain randomization by 36.2 percentage points. Gains over DAgger range from 11 to 24 percentage points across categories. These results support online residual dynamics learning as an effective approach to grasping policy transfer under the tested conditions.
