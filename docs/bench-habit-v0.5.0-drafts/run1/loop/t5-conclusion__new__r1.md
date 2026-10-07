## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. Residual dynamics are the difference between simulator-predicted and real-robot dynamics. AdaptRL learns this difference during deployment and corrects the policy for it.

Across the five object categories in Table 5 (100 real-robot trials each), AdaptRL achieves the highest grasp success. Its mean over the five categories is 82.2%, compared with 63.0% for DAgger and 46.0% for domain randomization. AdaptRL's advantage over DAgger is smallest on rigid objects (11 points) and larger on every other category (18 to 24 points). Against domain randomization, the advantage is largest on reflective objects (44 points).

All three methods rank the categories in the same order, from rigid to transparent. Reflective and transparent objects remain the hardest for AdaptRL, at 79% and 68% success. The grasping results here leave transfer to other robot platforms and manipulation skills untested. Future work should identify the cause of the remaining failures on transparent and reflective objects, and test whether residual dynamics learned online transfer to other robots and tasks.
