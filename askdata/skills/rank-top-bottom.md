# rank-top-bottom

## Description
Rank items by a metric and select the top or bottom N results. Always use ORDER BY + LIMIT, never fetch all rows and pick manually.

## When to Use
- "Which X has the most/least Y?"
- "Top N by Z"
- "Bottom N with lowest W"
- "Rank schools by score" (use RANK() or ROW_NUMBER() window function)

## SQL Pattern
```sql
-- For single result (which is the most/least):
SELECT <columns>
FROM <table>
[WHERE <filters>]
ORDER BY <metric_column> DESC  -- or ASC for least/lowest
LIMIT 1

-- For top/bottom N with rank:
SELECT <columns>,
  RANK() OVER (ORDER BY <metric_column> DESC) AS rank
FROM <table>
[WHERE <filters>]
ORDER BY rank
LIMIT <N>
```

## Example
Question: "Which county has the most schools that do not offer physical building?"
```sql
SELECT County, COUNT(*) AS school_count
FROM schools
WHERE Virtual = 'F' AND County IN ('San Diego', 'Santa Barbara')
GROUP BY County
ORDER BY school_count DESC
LIMIT 1
```
