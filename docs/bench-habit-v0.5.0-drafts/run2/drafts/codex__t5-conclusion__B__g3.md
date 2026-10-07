## Conclusion

We presented AdaptRL, which transfers grasping policies from simulation to a real robot by learning residual dynamics online. These learned corrections model discrepancies between simulated and real dynamics.

Across 100 real-robot trials per object category, AdaptRL achieves higher grasp success than domain randomization and DAgger in all five categories (Table 5). Its advantage over DAgger ranges from 11 to 24 percentage points. Transparent objects remain the weakest category, with 68% success compared with 94% for rigid objects. These results support online residual dynamics learning for grasping policy transfer across the tested categories, while identifying transparent-object grasping as a remaining challenge.
