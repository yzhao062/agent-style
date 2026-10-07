## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. Residual dynamics are the difference between simulator-predicted and real-robot dynamics. AdaptRL learns this difference during deployment and corrects the policy for it.

Across the five object categories in Table 5 (100 real-robot trials each), AdaptRL achieves the highest grasp success. Its mean over the five categories is 82.2%, compared with 63.0% for DAgger and 46.0% for domain randomization. The gain over DAgger is smallest on rigid objects (11 points, 94% versus 83%) and ranges from 18 to 24 points on the other four categories. Gains over domain randomization range from 23 points on rigid objects to 44 points on reflective objects.

Absolute success remains well below 100% on the hardest categories. All three methods decline in the same order, from rigid to transparent objects, and AdaptRL fails 21% of reflective-object trials and 32% of transparent-object trials. We tested one robot on one task, grasping, so transfer to other platforms and manipulation skills is unverified. Future work should identify the cause of the remaining failures on transparent and reflective objects, and test whether residual dynamics learned online transfer to other robots and tasks.
