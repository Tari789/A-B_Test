"""
A/B test analysis.

Runs the randomisation check, primary and secondary statistical tests,
effect size, and guardrail evaluation, then prints a ship/no-ship decision.
"""

import os
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest, proportion_effectsize

ALPHA = 0.05
MDE_ABSOLUTE = 0.02       # Must match the value used in power_analysis.py
REVENUE_PER_TRIP_USD = 4.50   # Assumed platform margin per trip

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "experiment_data.csv",
)


def section(title):
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def randomisation_check(df):
    """
    Verify the two groups are balanced on a pre-experiment covariate.

    If randomisation failed, any downstream result is unreliable — so this
    runs before we look at the outcome metric.
    """
    section("1. RANDOMISATION CHECK (pre-experiment covariate)")

    control = df.loc[df["group"] == "control", "prior_week_trips"]
    treatment = df.loc[df["group"] == "treatment", "prior_week_trips"]

    t_stat, p_value = stats.ttest_ind(control, treatment, equal_var=False)

    print(f"Control mean prior-week trips:   {control.mean():.3f}")
    print(f"Treatment mean prior-week trips: {treatment.mean():.3f}")
    print(f"Welch t-test p-value:            {p_value:.4f}")

    if p_value < ALPHA:
        print("\n  WARNING: groups differ significantly on a pre-experiment")
        print("  covariate. Randomisation may have failed — investigate before")
        print("  trusting the results below.")
    else:
        print("\n  PASS — no significant pre-existing difference between groups.")

    return p_value >= ALPHA


def primary_test(df):
    """Two-proportion z-test on weekly active rate."""
    section("2. PRIMARY METRIC — Weekly Active Rate")

    grouped = df.groupby("group")["is_active"].agg(["sum", "count"])
    c_success, c_n = grouped.loc["control", "sum"], grouped.loc["control", "count"]
    t_success, t_n = grouped.loc["treatment", "sum"], grouped.loc["treatment", "count"]

    c_rate = c_success / c_n
    t_rate = t_success / t_n
    abs_diff = t_rate - c_rate
    rel_lift = abs_diff / c_rate

    z_stat, p_value = proportions_ztest(
        count=np.array([t_success, c_success]),
        nobs=np.array([t_n, c_n]),
        alternative="two-sided",
    )

    # 95% CI on the absolute difference (unpooled standard error)
    se = np.sqrt(c_rate * (1 - c_rate) / c_n + t_rate * (1 - t_rate) / t_n)
    z_crit = stats.norm.ppf(1 - ALPHA / 2)
    ci_low, ci_high = abs_diff - z_crit * se, abs_diff + z_crit * se

    cohens_h = proportion_effectsize(t_rate, c_rate)

    print(f"Control:    {c_success:,} / {c_n:,} = {c_rate:.4f}")
    print(f"Treatment:  {t_success:,} / {t_n:,} = {t_rate:.4f}")
    print("-" * 64)
    print(f"Absolute difference:  {abs_diff:+.4f}  ({abs_diff * 100:+.2f} pp)")
    print(f"Relative lift:        {rel_lift:+.2%}")
    print(f"95% CI (absolute):    [{ci_low:+.4f}, {ci_high:+.4f}]")
    print(f"z-statistic:          {z_stat:.4f}")
    print(f"p-value:              {p_value:.6f}")
    print(f"Effect size (h):      {cohens_h:.4f}")

    significant = p_value < ALPHA
    print(f"\nStatistically significant at alpha={ALPHA}: {significant}")
    print(f"Exceeds MDE of {MDE_ABSOLUTE:.1%}: {abs_diff >= MDE_ABSOLUTE}")

    return {
        "significant": significant,
        "abs_diff": abs_diff,
        "ci_low": ci_low,
        "exceeds_mde": abs_diff >= MDE_ABSOLUTE,
    }


def secondary_test(df):
    """Welch's t-test on trips per driver."""
    section("3. SECONDARY METRIC — Trips per Driver")

    control = df.loc[df["group"] == "control", "trips_completed"]
    treatment = df.loc[df["group"] == "treatment", "trips_completed"]

    # Welch's t-test — does not assume equal variances between groups
    t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)

    diff = treatment.mean() - control.mean()

    # Cohen's d using pooled standard deviation
    pooled_sd = np.sqrt((control.var(ddof=1) + treatment.var(ddof=1)) / 2)
    cohens_d = diff / pooled_sd if pooled_sd > 0 else 0.0

    print(f"Control mean trips:    {control.mean():.3f} (sd {control.std():.3f})")
    print(f"Treatment mean trips:  {treatment.mean():.3f} (sd {treatment.std():.3f})")
    print("-" * 64)
    print(f"Difference:            {diff:+.3f} trips per driver")
    print(f"Welch t-statistic:     {t_stat:.4f}")
    print(f"p-value:               {p_value:.6f}")
    print(f"Effect size (d):       {cohens_d:.4f}")
    print(f"\nStatistically significant at alpha={ALPHA}: {p_value < ALPHA}")

    return {"significant": p_value < ALPHA, "diff": diff}


def guardrail_check(df, secondary):
    """Does the incremental volume justify the incentive spend?"""
    section("4. GUARDRAIL — Incentive Cost vs Incremental Revenue")

    n_treatment = (df["group"] == "treatment").sum()
    total_incentive = df["incentive_paid_usd"].sum()

    incremental_trips = secondary["diff"] * n_treatment
    incremental_revenue = incremental_trips * REVENUE_PER_TRIP_USD
    net = incremental_revenue - total_incentive

    cost_per_incremental_trip = (
        total_incentive / incremental_trips if incremental_trips > 0 else float("inf")
    )

    print(f"Treatment drivers:            {n_treatment:,}")
    print(f"Total incentive paid:         ${total_incentive:,.2f}")
    print(f"Incremental trips:            {incremental_trips:,.0f}")
    print(f"Cost per incremental trip:    ${cost_per_incremental_trip:,.2f}")
    print(f"Assumed revenue per trip:     ${REVENUE_PER_TRIP_USD:,.2f}")
    print(f"Incremental revenue:          ${incremental_revenue:,.2f}")
    print("-" * 64)
    print(f"Net impact:                   ${net:,.2f}")

    passes = cost_per_incremental_trip < REVENUE_PER_TRIP_USD
    print(f"\nGuardrail {'PASS' if passes else 'FAIL'} — incentive "
          f"{'pays back' if passes else 'costs more than it returns'}.")

    return {"passes": passes, "net": net}


def recommendation(primary, guardrail):
    section("5. RECOMMENDATION")

    if not primary["significant"]:
        print("DO NOT SHIP — no statistically significant effect detected.")
        print("Before concluding the intervention doesn't work, confirm the")
        print("test was adequately powered to detect an effect of MDE size.")
    elif not primary["exceeds_mde"]:
        print("DO NOT SHIP — effect is statistically significant but below the")
        print(f"{MDE_ABSOLUTE:.1%} minimum needed to justify the incentive cost.")
        print("A real but economically immaterial effect.")
    elif not guardrail["passes"]:
        print("DO NOT SHIP — the lift is real and meaningful, but the incentive")
        print("costs more per incremental trip than the trip returns.")
        print("Consider a lower bonus or a higher qualifying threshold.")
    else:
        print("SHIP — statistically significant, exceeds the minimum effect")
        print("worth acting on, and the incentive spend pays back.")
        print(f"\nLower bound of the 95% CI is {primary['ci_low']:+.4f}, so even")
        print("the conservative estimate of the effect remains positive.")

    print()
    print("Caveats: single one-week window, so a novelty effect cannot be ruled")
    print("out. A longer holdout would be needed to confirm the change is durable.")


def main():
    if not os.path.exists(DATA_PATH):
        raise SystemExit(
            f"Data not found at {DATA_PATH}\nRun: python src/generate_data.py"
        )

    df = pd.read_csv(DATA_PATH)

    print("A/B TEST ANALYSIS — Driver Incentive Experiment")
    print(f"Loaded {len(df):,} drivers")

    randomisation_check(df)
    primary = primary_test(df)
    secondary = secondary_test(df)
    guardrail = guardrail_check(df, secondary)
    recommendation(primary, guardrail)
    print()


if __name__ == "__main__":
    main()
