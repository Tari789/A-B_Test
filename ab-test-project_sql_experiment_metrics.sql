-- ============================================================
-- Experiment Metrics Aggregation
-- ============================================================
-- How the A/B test metrics would be computed in a warehouse,
-- rather than in pandas. Presto/Trino syntax.
--
-- Generic table and column names — illustrative only.
-- ============================================================

WITH
  -- Experiment assignment: one row per driver, fixed at enrolment.
  -- Deduplicated defensively in case of double-logging.
  assignments AS (
    SELECT DISTINCT
      driver_id,
      experiment_group,
      enrolled_at
    FROM
      warehouse.experiment_assignments
    WHERE
      experiment_name = 'driver_completion_bonus_v1'
      AND enrolled_at >= DATE '2026-01-06'
  ),

  -- Pre-experiment covariate, used for the randomisation balance check.
  -- Measured strictly BEFORE enrolment so it cannot be affected by treatment.
  pre_period AS (
    SELECT
      a.driver_id,
      COUNT(t.transaction_id) AS prior_week_trips
    FROM
      assignments a
      LEFT JOIN warehouse.fact_transactions t
        ON t.supply_id = a.driver_id
        AND t.event_date >= DATE_ADD('day', -7, DATE(a.enrolled_at))
        AND t.event_date <  DATE(a.enrolled_at)
        AND t.is_completed = TRUE
    GROUP BY 1
  ),

  -- Outcome metrics over the experiment window.
  experiment_period AS (
    SELECT
      a.driver_id,
      a.experiment_group,
      COUNT(t.transaction_id) AS trips_completed,
      -- Binary primary metric: did the driver complete any trip?
      CASE WHEN COUNT(t.transaction_id) > 0 THEN 1 ELSE 0 END AS is_active
    FROM
      assignments a
      LEFT JOIN warehouse.fact_transactions t
        ON t.supply_id = a.driver_id
        AND t.event_date >= DATE(a.enrolled_at)
        AND t.event_date <  DATE_ADD('day', 7, DATE(a.enrolled_at))
        AND t.is_completed = TRUE
    GROUP BY 1, 2
  ),

  -- Incentive spend, joined separately so drivers with no payout
  -- still appear with zero rather than being dropped.
  incentive_spend AS (
    SELECT
      driver_id,
      SUM(payout_amount_usd) AS incentive_paid_usd
    FROM
      warehouse.fact_incentive_payouts
    WHERE
      incentive_program = 'driver_completion_bonus_v1'
    GROUP BY 1
  )

SELECT
  e.experiment_group,
  COUNT(DISTINCT e.driver_id)                       AS n_drivers,

  -- Primary metric
  SUM(e.is_active)                                  AS active_drivers,
  AVG(CAST(e.is_active AS DOUBLE))                  AS active_rate,

  -- Secondary metric
  AVG(CAST(e.trips_completed AS DOUBLE))            AS mean_trips_per_driver,
  STDDEV(CAST(e.trips_completed AS DOUBLE))         AS stddev_trips_per_driver,

  -- Randomisation balance check
  AVG(CAST(p.prior_week_trips AS DOUBLE))           AS mean_prior_week_trips,

  -- Guardrail
  COALESCE(SUM(i.incentive_paid_usd), 0)            AS total_incentive_usd,
  COALESCE(SUM(i.incentive_paid_usd), 0)
    / NULLIF(SUM(e.trips_completed), 0)             AS incentive_cost_per_trip

FROM
  experiment_period e
  LEFT JOIN pre_period      p ON p.driver_id = e.driver_id
  LEFT JOIN incentive_spend i ON i.driver_id = e.driver_id
GROUP BY
  1
ORDER BY
  1;
