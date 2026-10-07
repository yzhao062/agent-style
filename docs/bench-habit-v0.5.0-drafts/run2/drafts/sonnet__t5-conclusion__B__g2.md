## Conclusion

AdaptRL transfers grasping policies from simulation to a real robot by learning residual dynamics online. Residual dynamics are the differences between the simulator's predicted object behavior and the behavior the robot observes. We tested AdaptRL against domain randomization and DAgger on five object categories, with 100 real-robot grasp trials per category. AdaptRL achieved the highest success rate in every category (Table 5).

Compared with domain randomization, AdaptRL's gain grows from 23 points on rigid objects to 44 points on reflective objects. Over DAgger, the stronger baseline, the gain grows from 11 points on rigid objects to 24 points on reflective objects. It exceeds 20 points on jointed, reflective, and transparent objects. The two baselines lose the most accuracy on the categories where AdaptRL gains the most, which suggests that online residual correction matters most when the simulator mispredicts real object behavior.

Transparent objects remain the open problem. AdaptRL reaches 68% there, so 32% of grasps still fail, against 6% for rigid objects. All three methods score lowest on this category (28%, 46%, and 68%), which makes it the target for future work.
