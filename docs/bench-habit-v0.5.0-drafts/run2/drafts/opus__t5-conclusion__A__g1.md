## Conclusion

We presented AdaptRL, which transfers grasping policies from simulation to a real robot by learning residual dynamics online. The residual model captures the difference between simulated and real dynamics, and AdaptRL updates it with data the robot collects during deployment.

Across 100 real-robot trials per object category (Table 5), AdaptRL achieved the highest grasp success in all five categories. Pooled over the 500 trials, it succeeded 82.2% of the time, against 63.0% for DAgger and 46.0% for domain randomization. All three methods do best on rigid objects, and that is also where AdaptRL's margin over DAgger is smallest (11 points). On the other four categories, the margin ranges from 18 to 24 points. Gains over domain randomization peak on the two categories where it transfers worst: reflective objects (+44 points) and transparent objects (+40), compared with +23 on rigid objects.

Transparent objects remain the hardest category, and AdaptRL still fails in 32 of 100 trials on them. A residual dynamics model corrects errors in predicted motion and does not change how the robot perceives the object. Standard depth sensors produce inaccurate depth on transparent surfaces (Sajjan et al., 2020), so some of these failures may come from perception. Separating perception failures from dynamics failures on transparent and reflective objects would show whether pairing AdaptRL with depth completion, as in ClearGrasp, raises success on these two categories.

This paper evaluates AdaptRL on grasping alone. Future work should test whether learning residual dynamics online gives similar gains on contact-rich tasks such as peg insertion and in-hand reorientation.
