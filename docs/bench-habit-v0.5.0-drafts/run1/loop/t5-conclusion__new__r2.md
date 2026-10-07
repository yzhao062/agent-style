## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. Residual dynamics are the difference between simulator-predicted and real-robot dynamics, which AdaptRL learns during deployment.

Across the five object categories in Table 5 (100 real-robot trials each), AdaptRL achieves the highest grasp success. Its mean over the five categories is 82.2%, compared with 63.0% for DAgger and 46.0% for domain randomization. AdaptRL's advantage over DAgger is smallest on rigid objects and larger in the other four categories. Its largest gain over domain randomization occurs on reflective objects.

All three methods rank the categories in the same order, from rigid to transparent. Reflective and transparent objects nevertheless remain AdaptRL's hardest tested categories. The grasping results here leave transfer to other robot platforms and manipulation skills untested. Future work should identify the cause of the remaining failures on transparent and reflective objects, and test whether residual dynamics learned online transfer to other robots and tasks.
