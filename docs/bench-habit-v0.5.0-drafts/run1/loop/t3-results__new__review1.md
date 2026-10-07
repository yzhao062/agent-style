1. **Opening claim is miscalibrated.** Dice is numerically higher on all three tasks; two show statistically supported gains. State this distinction explicitly. Suggested rewrite: “MedNeXt-Lite achieves statistically supported Dice gains over nnU-Net on cardiac and lung tasks, while the brain comparison remains inconclusive (Table 3).”

2. **Cardiac and lung sentences transcribe Table 3.** Reporting both scores, differences, intervals, and p-values obscures the pattern. Suggested rewrite: “The gain over nnU-Net is largest for left-ventricle segmentation, with a smaller but statistically supported improvement for lung lesions.”

3. **Brain discussion repeats table values and becomes verbose.** The sentence beginning “The interval” exceeds 30 words. Explain the uncertainty directly without implying equivalence or treating confidence limits as absolute bounds. Suggested rewrite: “For glioma-core segmentation, the estimated gain is small, and the confidence interval includes both a modest loss and a modest improvement.”

4. **SwinUNETR comparison has an ambiguous pronoun and repeats numbers.** “Exceeds it” could refer to nnU-Net, although the stated gaps are against SwinUNETR. Suggested rewrite: “SwinUNETR scores remain close to nnU-Net across tasks. MedNeXt-Lite scores higher than SwinUNETR on cardiac and lung tasks, but Table 3 provides no direct significance tests for these comparisons.”

5. **“7.6 times fewer” is ambiguous and weakens the efficiency contribution.** Express the parameter reduction clearly and connect it to the supported accuracy result. Suggested rewrite: “MedNeXt-Lite achieves these cardiac and lung gains with approximately 87% fewer parameters than nnU-Net (4.1M versus 31M).”
