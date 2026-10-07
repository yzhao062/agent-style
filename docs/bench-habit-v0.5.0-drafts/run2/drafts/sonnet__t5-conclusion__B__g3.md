## Conclusion

AdaptRL transfers grasping policies from simulation to a real robot. It learns residual dynamics online, where the residual is the part of each real transition that the simulator fails to predict.

In 100 real-robot trials per object category, AdaptRL outperformed both domain randomization and DAgger, an imitation-learning baseline, on all five categories (Table 5). Success ranged from 94% on rigid objects to 68% on transparent objects. The margin over DAgger, the stronger baseline, is smallest on rigid objects at 11 points and reaches 21 to 24 points on jointed, reflective, and transparent objects. Domain randomization trails AdaptRL by 23 points on rigid objects and by 36 to 44 points on the other four categories.

Transparent objects remain the weakest case: AdaptRL fails on 32 of 100 grasps there, against 6 of 100 on rigid objects.
