# compare-periods

## Description
Compare a metric between two time periods (e.g., this month vs last month, year-over-year). Return both values and the absolute or percentage change.

## When to Use
- "How did X change between [period A] and [period B]?"
- "Compare revenue last month vs the month before"
- "Year-over-year growth of X"
- "Difference in X between [time A] and [time B]"

## SQL Pattern
```sql
SELECT
  SUM(CASE WHEN <time_column> BETWEEN '<period_a_start>' AND '<period_a_end>' THEN <metric_column> ELSE 0 END) AS period_a_value,
  SUM(CASE WHEN <time_column> BETWEEN '<period_b_start>' AND '<period_b_end>' THEN <metric_column> ELSE 0 END) AS period_b_value,
  SUM(CASE WHEN <time_column> BETWEEN '<period_a_start>' AND '<period_a_end>' THEN <metric_column> ELSE 0 END)
    - SUM(CASE WHEN <time_column> BETWEEN '<period_b_start>' AND '<period_b_end>' THEN <metric_column> ELSE 0 END) AS absolute_change,
  ROUND(
    (CAST(SUM(CASE WHEN <time_column> BETWEEN '<period_a_start>' AND '<period_a_end>' THEN <metric_column> ELSE 0 END) AS REAL)
     - SUM(CASE WHEN <time_column> BETWEEN '<period_b_start>' AND '<period_b_end>' THEN <metric_column> ELSE 0 END))
    * 100.0 / NULLIF(SUM(CASE WHEN <time_column> BETWEEN '<period_b_start>' AND '<period_b_end>' THEN <metric_column> ELSE 0 END), 0),
  2) AS pct_change
FROM <table>
```

## Example
Question: "Compare transaction volume between August and September 2013"
```sql
SELECT
  SUM(CASE WHEN Date BETWEEN '201308' AND '201308' THEN Consumption ELSE 0 END) AS aug_consumption,
  SUM(CASE WHEN Date BETWEEN '201309' AND '201309' THEN Consumption ELSE 0 END) AS sep_consumption,
  SUM(CASE WHEN Date BETWEEN '201309' AND '201309' THEN Consumption ELSE 0 END)
    - SUM(CASE WHEN Date BETWEEN '201308' AND '201308' THEN Consumption ELSE 0 END) AS change,
  ROUND(
    (CAST(SUM(CASE WHEN Date BETWEEN '201309' AND '201309' THEN Consumption ELSE 0 END) AS REAL)
     - SUM(CASE WHEN Date BETWEEN '201308' AND '201308' THEN Consumption ELSE 0 END))
    * 100.0 / NULLIF(SUM(CASE WHEN Date BETWEEN '201308' AND '201308' THEN Consumption ELSE 0 END), 0),
  2) AS pct_change
FROM yearmonth
```
