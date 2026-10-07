## Conclusion

We presented AdaptRL, a method for transferring grasping policies from simulation to a real robot. AdaptRL learns residual dynamics online: as the robot grasps, it uses real interaction data to fit a correction to the simulator's dynamics model. Over 500 real-robot trials spanning five object categories, AdaptRL succeeds on 82.2% of grasps, compared with 63.0% for DAgger and 46.0% for domain randomization (Table 5).

The sim-to-real gap varies widely across object categories. Domain randomization, which trains only in simulation, succeeds on 71% of rigid-object grasps but at most 44% of jointed, reflective, and transparent ones. AdaptRL gains the most on the categories where that gap is largest. Its gain over the stronger baseline, DAgger, is 11 points on rigid objects and between 21 and 24 points on the three hardest categories.

Transparent objects remain the hardest category for all three methods. AdaptRL narrows the success-rate spread between rigid and transparent objects to 26 points, down from 37 for DAgger and 43 for domain randomization. It still fails 32 of 100 transparent-object grasps, more than a third of its 89 failures across all five categories.
