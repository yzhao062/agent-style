## Conclusion

AdaptRL transfers grasping policies from simulation to a real robot by learning residual dynamics online. The residual is the gap between simulated dynamics and the dynamics the robot observes. In 100 real-robot trials per object category, AdaptRL succeeds on 68% to 94% of grasps and outperforms both domain randomization and DAgger in all five categories (Table 5). The margin over DAgger widens from 11 points on rigid objects to 24 points on reflective objects, and stays at 22 points on transparent objects. Against domain randomization, the margin is 23 points on rigid objects and 36 to 44 points on the other four categories.

Transparent objects remain the hardest category, with AdaptRL succeeding on 68% of grasps. Roughly one grasp in three still fails, so improving transparent-object grasping is the main open problem for AdaptRL.
