## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. The residual is a learned correction for the gap between simulated and real dynamics, and AdaptRL updates it from real-robot data while the robot operates.

Across five object categories with 100 real-robot trials each, AdaptRL achieves the highest grasp success in every category (Table 5). Pooled over all 500 trials, it succeeds on 82% of grasps, compared with 63% for DAgger and 46% for domain randomization. Its margin over DAgger, the stronger baseline, grows as objects become harder to transfer. Rigid objects show the smallest gain: DAgger already reaches 83%, and AdaptRL adds 11 points. On jointed, reflective, and transparent objects, where DAgger succeeds on 61% of grasps or fewer, AdaptRL adds 21 to 24 points. These gains suggest that learning residual dynamics online helps most where policies trained in simulation transfer worst.

Transparent objects remain the hardest category. AdaptRL succeeds on 68% of transparent grasps, compared with 94% on rigid objects, so about one attempt in three still fails. Closing this 26-point gap is the clearest next target for online residual adaptation.
