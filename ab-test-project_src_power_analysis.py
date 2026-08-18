"""
Pre-experiment sample size calculation.

Run this BEFORE the experiment starts. Determines how many drivers are needed
per group to reliably detect the minimum effect worth acting on.
"""

import numpy as np
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

# --- Experiment parameters (set from the business case, not from data) ---
BASELINE_RATE = 0.62   # Current weekly active rate among drivers
MDE_ABSOLUTE = 0.02    # Minimum detectable effect: +2 percentage points
ALPHA = 0.05           # Significance level (two-tailed)
POWER = 0.80           # Probability of detecting a true effect of MDE size


def calculate_sample_size(baseline, mde, alpha=ALPHA, power=POWER):
    """
    Return the required sample size per group for a two-proportion test.

    Uses Cohen's h as the standardised effect size, which is the correct
    transformation for comparing two proportions.
    """
    treatment_rate = baseline + mde
    effect_size = proportion_effectsize(treatment_rate, baseline)

    analysis = NormalIndPower()
    n_per_group = analysis.solve_power(
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        ratio=1.0,
        alternative="two-sided",
    )
    return int(np.ceil(n_per_group)), effect_size


def main():
    n_per_group, effect_size = calculate_sample_size(BASELINE_RATE, MDE_ABSOLUTE)

    print("=" * 60)
    print("SAMPLE SIZE CALCULATION")
    print("=" * 60)
    print(f"Baseline active rate:      {BASELINE_RATE:.1%}")
    print(f"Target active rate:        {BASELINE_RATE + MDE_ABSOLUTE:.1%}")
    print(f"Minimum detectable effect: {MDE_ABSOLUTE:.1%} (absolute)")
    print(f"Significance level (alpha):{ALPHA}")
    print(f"Statistical power:         {POWER}")
    print(f"Effect size (Cohen's h):   {effect_size:.4f}")
    print("-" * 60)
    print(f"Required per group:        {n_per_group:,} drivers")
    print(f"Required total:            {n_per_group * 2:,} drivers")
    print("=" * 60)
    print()
    print("Note: this is fixed before the experiment begins. Checking for")
    print("significance repeatedly as data arrives ('peeking') inflates the")
    print("false-positive rate well above the nominal 5%.")


if __name__ == "__main__":
    main()
