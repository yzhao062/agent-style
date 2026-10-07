## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. The residual is the gap between the dynamics the simulator predicts and the dynamics the robot exhibits, and AdaptRL fits it from real-robot interaction during deployment.

Over 100 real-robot trials per object category (Table 5), AdaptRL reaches a mean grasp success of 82.2%, compared with 63.0% for DAgger and 46.0% for domain randomization. It leads in all five categories, by 11 to 24 points over DAgger and by 23 to 44 points over domain randomization. The margin over DAgger is 11 points on rigid objects and 18 to 24 points on the other four categories. The gain is therefore largest where the baselines succeed least.

Transparent objects remain the hardest category, with AdaptRL succeeding on 68% of trials. Diagnosing the remaining failures there is the next step.
