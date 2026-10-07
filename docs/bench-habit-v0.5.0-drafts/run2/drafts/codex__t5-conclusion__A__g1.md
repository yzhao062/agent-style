## Conclusion

We presented AdaptRL, which learns residual dynamics online to transfer grasping policies from simulation to a real robot. In Table 5, AdaptRL achieves higher grasp success than domain randomization and DAgger across all five object categories, with 100 trials per category. Mean success across categories reaches 82.2%, compared with 46.0% for domain randomization and 63.0% for DAgger. AdaptRL exceeds DAgger by 11 to 24 percentage points, with the largest gain on reflective objects.

These results support online residual dynamics learning for grasping policy transfer in the evaluated setting. Success still varies across categories, from 94% on rigid objects to 68% on transparent objects. Future work should investigate the remaining failures, measure variability across repeated evaluations, and test transfer across additional robots and object sets.
