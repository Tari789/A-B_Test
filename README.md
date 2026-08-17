# A-B_Test
A/B Test Analysis: Driver Incentive Experiment
An end-to-end A/B test analysis on a simulated two-sided marketplace experiment, from hypothesis and sample_size planning through to statistical testing, guardrail checks, and a ship/no_ship recommendation.

Built with synthetic data. No proprietary data or schemas are used.

---

## The scenario

A marketplace platform wants to increase driver engagement. The proposed intervention:

> **Offer drivers a completion bonus for finishing 10+ trips in a week.**

Before rolling this out, we need to know whether it actually works, and whether it costs more than it returns.

**Primary metric** - *Weekly active rate*: the proportion of drivers completing at least one trip in the week (binary >> two_proportion z_test)

**Secondary metric** - *Trips per driver*: average weekly trips (continuous → Welch's t_test)

**Guardrail metric** - *Cost per incremental trip*: does the incentive spend justify the volume gained?

---

## Hypotheses

| | |
|---|---|
| **H₀** | The incentive has no effect on weekly active rate (p_treatment = p_control) |
| **H₁** | The incentive changes the weekly active rate (p_treatment ≠ p_control) |
| **α** | 0.05 (two-tailed) |
| **Power** | 0.80 |
| **MDE** | 2 percentage points - the smallest lift worth the incentive cost |

The MDE is set from the business case, not from what the data happens to show. A lift smaller than 2pp wouldn't pay back the bonus spend, so detecting it isn't useful.

---

## Repository structure

```
ab-test-project/
├── README.md
├── requirements.txt
├── src/
│   ├── generate_data.py      # Creates synthetic experiment data
│   ├── power_analysis.py     # Pre-experiment sample size calculation
│   └── analysis.py           # Statistical tests + results
├── sql/
│   └── experiment_metrics.sql   # How metrics would be aggregated in a warehouse
└── data/
    └── experiment_data.csv   # Generated output
```

---

## Running it

```bash
pip install -r requirements.txt

python src/power_analysis.py     # How many drivers do we need?
python src/generate_data.py      # Simulate the experiment
python src/analysis.py           # Analyse the results
```

---

## Method

**1. Sample size first.** Calculated *before* looking at any data, using the baseline rate, target MDE, α and power. Running a test without this risks being underpowered, finding nothing when a real effect exists.

**2. Randomisation check (A/A sanity).** Before testing the outcome, confirm the two groups are balanced on a pre-experiment covariate (prior-week trips). If randomisation failed, nothing downstream is trustworthy.

**3. Primary test.** Two-proportion z-test on active rate, reported with a 95% confidence interval on the absolute difference — not just a p-value.

**4. Secondary test.** Welch's t-test on trips per driver (Welch rather than Student's, since equal variance between groups isn't a safe assumption).

**5. Effect size.** Cohen's h for the proportion difference. A statistically significant result on a large sample can still be practically meaningless — effect size makes that visible.

**6. Guardrail.** Incremental trips are weighed against total incentive spend. A lift that costs more than it earns is not a win.

---

## Interpreting the output

The analysis prints a decision framework rather than a bare p-value:

- **Significant + above MDE + guardrail passes** → ship
- **Significant + below MDE** → real but too small to justify cost
- **Not significant** → insufficient evidence; check whether the test was adequately powered before concluding "no effect"

---

## Notes on what this deliberately does *not* do

- **No peeking / early stopping.** Sample size is fixed up front. Repeatedly checking significance as data arrives inflates the false-positive rate well above the nominal 5%.
- **No multiple-comparison correction**, because there is a single pre-declared primary metric. If several primary metrics were tested, a Bonferroni or Benjamini–Hochberg adjustment would be required.
- **No novelty-effect handling.** A one-week window may capture a temporary behavioural spike rather than a durable change; a longer holdout would be needed to distinguish them.

These are stated explicitly because knowing the limits of an analysis matters as much as running it.

---

## Tech

Python (pandas, numpy, scipy, statsmodels) · SQL (Presto/Trino-style)
