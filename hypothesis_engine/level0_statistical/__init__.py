"""
Level 0: Statistical Foundation.

For every (pair, timeframe, session, direction) pocket, compute:
  - Sample size, mean forward return at 1/5/20/50 bars
  - Bootstrap confidence intervals against zero
  - Win rate, t-stat, effect size

Only pockets with statistically significant edge survive to Level 1.
"""
