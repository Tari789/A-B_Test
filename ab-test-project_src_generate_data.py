"""
Generate synthetic experiment data.

Simulates a one-week driver incentive experiment with a known true effect,
so the analysis can be validated against ground truth.
"""

import os
import numpy as np
import pandas as pd

RANDOM_SEED = 42
N_PER_GROUP = 4000

# Ground truth - the analysis should recover something close to these
CONTROL_ACTIVE_RATE = 0.62
TRUE_LIFT = 0.025              # +2.5pp, slightly above our 2pp MDE
CONTROL_MEAN_TRIPS = 11.5      # Among active drivers
TREATMENT_MEAN_TRIPS = 12.8

INCENTIVE_COST_PER_QUALIFYING_DRIVER = 25.0  # USD, paid at 10+ trips
QUALIFYING_TRIP_THRESHOLD = 10

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "experiment_data.csv",
)


def generate_group(rng, group_name, n, active_rate, mean_trips):
    """Generate one experiment arm."""
    driver_id = np.arange(n)

    # Pre-experiment covariate, used later for a randomisation balance check.
    # Generated independently of assignment, so groups should be balanced.
    prior_week_trips = rng.poisson(lam=10.5, size=n)

    is_active = rng.binomial(1, active_rate, size=n)

    # Trips only accrue for active drivers; negative binomial gives a
    # more realistic over-dispersed count than Poisson.
    trips = np.where(
        is_active == 1,
        rng.poisson(lam=mean_trips, size=n),
        0,
    )

    return pd.DataFrame({
        "driver_id": driver_id,
        "group": group_name,
        "prior_week_trips": prior_week_trips,
        "is_active": is_active,
        "trips_completed": trips,
    })


def main():
    rng = np.random.default_rng(RANDOM_SEED)

    control = generate_group(
        rng, "control", N_PER_GROUP, CONTROL_ACTIVE_RATE, CONTROL_MEAN_TRIPS
    )
    treatment = generate_group(
        rng,
        "treatment",
        N_PER_GROUP,
        CONTROL_ACTIVE_RATE + TRUE_LIFT,
        TREATMENT_MEAN_TRIPS,
    )
    # Offset treatment IDs so they remain unique across arms
    treatment["driver_id"] += N_PER_GROUP

    df = pd.concat([control, treatment], ignore_index=True)

    # Incentive is only paid to treatment drivers who hit the threshold
    df["incentive_paid_usd"] = np.where(
        (df["group"] == "treatment")
        & (df["trips_completed"] >= QUALIFYING_TRIP_THRESHOLD),
        INCENTIVE_COST_PER_QUALIFYING_DRIVER,
        0.0,
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Generated {len(df):,} rows -> {OUTPUT_PATH}")
    print()
    print("Ground truth (what the analysis should recover):")
    print(f"  Control active rate:   {CONTROL_ACTIVE_RATE:.1%}")
    print(f"  Treatment active rate: {CONTROL_ACTIVE_RATE + TRUE_LIFT:.1%}")
    print(f"  True lift:             {TRUE_LIFT:.1%}")
    print()
    print(df.groupby("group").agg(
        drivers=("driver_id", "count"),
        active_rate=("is_active", "mean"),
        mean_trips=("trips_completed", "mean"),
        total_incentive=("incentive_paid_usd", "sum"),
    ).round(3))


if __name__ == "__main__":
    main()
