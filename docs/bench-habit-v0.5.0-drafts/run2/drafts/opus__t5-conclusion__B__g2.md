## Conclusion

We presented AdaptRL, which transfers grasping policies from simulation to a real robot by learning residual dynamics online. The residual model is a learned correction to the simulator's dynamics. AdaptRL fits it to data the robot collects while grasping, so the policy adapts to the physical system as it runs.

Over 100 real-robot trials per object category, AdaptRL achieved the highest grasp success in all five categories (Table 5). DAgger is the stronger baseline, and AdaptRL's lead over it grows as objects get harder to grasp. The gap is 11 percentage points on rigid objects and 18-24 points on deformable, jointed, reflective, and transparent objects. Over domain randomization, the gap ranges from 23 to 44 points. The largest gains come in the categories where both baselines fail most often. This pattern suggests that online residual learning helps most where simulated and real behavior differ most.

Transparent objects remain the weakest case. AdaptRL more than halves DAgger's failure rate on the other four categories, but on transparent objects it reduces failures only from 54 to 32 per 100 trials. At 68% success, roughly one transparent-object grasp in three still fails.
