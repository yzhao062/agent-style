## Conclusion

We presented AdaptRL, which transfers grasping policies from simulation to a real robot by learning residual dynamics online. Residual dynamics are the differences between the transitions a simulator predicts and the transitions the robot produces. AdaptRL learns a correction for these differences from real-robot interaction.

Over 100 real-robot trials per object category, AdaptRL averages 82.2% grasp success across the five categories, against 63.0% for DAgger and 46.0% for domain randomization (Table 5). The advantage holds in every category. Its margin over DAgger is 11 points on rigid objects and 18 to 24 points on the other four categories. The largest margins, 21 to 24 points, fall on jointed, reflective, and transparent objects, where DAgger scores lowest. This pattern suggests that the benefit of online correction grows with the sim-to-real gap the baselines leave open.

Transparent objects remain the hardest category at 68% grasp success, so about one in three grasps still fails there. Raising transparent-object grasp success is our next target for AdaptRL.
