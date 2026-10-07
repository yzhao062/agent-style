## Conclusion

We presented AdaptRL, a method that learns residual dynamics online to transfer grasping policies from simulation to a real robot. In 100 real-robot trials per object category (Table 5), AdaptRL reached 82.2% mean grasp success over five categories, against 63.0% for DAgger and 46.0% for domain randomization. It beat both baselines in every category.

Gains over both baselines are smallest on rigid objects and largest on reflective objects. AdaptRL leads DAgger by 11 points on rigid objects (94% versus 83%) and by 24 points on reflective objects (79% versus 55%). The lead over domain randomization grows from 23 points to 44 points between the same two categories. This pattern is consistent with a larger simulation-to-real dynamics gap on the harder categories, though Table 5 does not isolate the cause.

Success remains lowest on transparent objects, where AdaptRL fails in 32 of 100 trials, and on reflective objects, where it fails in 21 of 100. We suspect that perception error on these surfaces accounts for part of the failures, because a residual dynamics model cannot correct what the policy fails to see. We evaluated only grasping. Next steps are to extend AdaptRL to other manipulation skills and to pair it with perception adaptation for transparent and reflective objects.
