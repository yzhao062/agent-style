## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. The residual is a correction to the simulator's dynamics model, which AdaptRL fits from the robot's own interactions during deployment. AdaptRL therefore learns the mismatch between simulated and real physics while the robot operates, whereas domain randomization must anticipate that mismatch during training.

In 100 real-robot trials per object category, AdaptRL achieves the highest grasp success in all five categories (Table 5). Its advantage over DAgger, the stronger baseline, widens from 11 percentage points on rigid objects to 21-24 points on jointed, reflective, and transparent objects. AdaptRL also loses less success as objects get harder to grasp. From rigid to transparent objects, its success falls by 26 points, compared with 37 points for DAgger and 43 for domain randomization.

Reflective and transparent objects remain the hardest categories for all three methods. Even with AdaptRL, 21% of reflective grasps and 32% of transparent grasps fail, which makes these two categories the clearest targets for future work.
