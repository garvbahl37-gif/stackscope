-- =============================================================================================
-- Reusable SQL macros (persisted in the warehouse catalog, usable from the SQL Lab)
-- =============================================================================================

-- Wilson score interval for a proportion p observed on n trials (95%, z = 1.959964).
-- For weighted estimates pass the Kish effective sample size as n.
CREATE OR REPLACE MACRO wilson_lo(p, n) AS
    CASE WHEN n > 0 THEN
        greatest(0.0, ((p + 1.920729 / n) - 1.959964 * sqrt(p * (1 - p) / n + 0.960365 / (n * n))) / (1 + 3.841459 / n))
    END;

CREATE OR REPLACE MACRO wilson_hi(p, n) AS
    CASE WHEN n > 0 THEN
        least(1.0, ((p + 1.920729 / n) + 1.959964 * sqrt(p * (1 - p) / n + 0.960365 / (n * n))) / (1 + 3.841459 / n))
    END;

-- Kish effective sample size from the sum of weights and the sum of squared weights.
CREATE OR REPLACE MACRO kish_n(sw, sw2) AS CASE WHEN sw2 > 0 THEN sw * sw / sw2 END;

CREATE OR REPLACE MACRO safe_div(a, b) AS CASE WHEN b > 0 THEN a / b END;
