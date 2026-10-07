## Conclusion

We presented AdaptRL, a method that transfers grasping policies from simulation to a real robot by learning residual dynamics online. Residual dynamics are the difference between simulated and real transitions. Across five object categories with 100 real-robot trials each, AdaptRL succeeds in 82.2% of the 500 trials, against 63.0% for DAgger and 46.0% for domain randomization. It also has the highest success rate in every category (Table 5).

The gain over DAgger is smallest on rigid objects (94% versus 83%, 11 points). The other four categories gain 18 to 24 points, with the largest on reflective objects (79% versus 55%). Against domain randomization, gains range from 23 points on rigid objects to 44 on reflective objects. Table 5 alone does not isolate the mechanism, but the larger gains on the harder categories suggest that online residual correction helps most where the simulation-to-real mismatch is largest.

Two limitations remain. Transparent objects still fail in 32 of 100 trials and reflective objects in 21 of 100. Each rate also rests on 100 trials, so its 95% binomial interval spans roughly ±9 points at 68% and ±5 points at 94%. Closing the remaining failures on transparent and reflective objects is the most direct next step. Evaluating more robots and more objects per category would test whether the gains generalize.
