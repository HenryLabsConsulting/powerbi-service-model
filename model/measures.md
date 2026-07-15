# DAX Measure Library

Every measure in the model, grouped by what it answers. The full definitions
live in [`model.tmdl`](model.tmdl). The values shown are for the committed
sample data and are the same numbers the validation harness asserts in CI.

Measures build on each other. Base measures are defined once, and the rest
reference them, so the logic stays consistent and easy to change in one place.

## Revenue and margin

| Measure | DAX | Value |
|---|---|---|
| Total Revenue | `SUM(fact_jobs[revenue])` | $2,332,041 |
| Total Cost | `SUM(fact_jobs[cost])` | $1,320,494 |
| Gross Margin | `[Total Revenue] - [Total Cost]` | $1,011,547 |
| Gross Margin % | `DIVIDE([Gross Margin], [Total Revenue])` | 43.4% |

## Volume and quality

| Measure | DAX | Value |
|---|---|---|
| Job Count | `COUNTROWS(fact_jobs)` | 2,274 |
| Completed Jobs | `CALCULATE([Job Count], fact_jobs[status] = "Completed")` | 1,840 |
| Canceled Jobs | `CALCULATE([Job Count], fact_jobs[status] = "Canceled")` | 187 |
| Cancellation Rate | `DIVIDE([Canceled Jobs], [Job Count])` | 8.2% |
| Average Ticket | `DIVIDE([Total Revenue], [Completed Jobs])` | $1,267 |
| First-Time-Fix Rate | `DIVIDE(CALCULATE([Completed Jobs], fact_jobs[first_time_fix] = 1), [Completed Jobs])` | 70.3% |
| Average Job Duration | `AVERAGE(fact_jobs[duration_min])` | 160 min |

First-time-fix rate is the quality measure that protects margin. A callback is a
second truck roll on the same job, so it carries cost with no new revenue.

## Workforce

| Measure | DAX | Value |
|---|---|---|
| Active Technicians | `DISTINCTCOUNT(fact_jobs[technician_key])` | 16 |
| Revenue per Technician | `DIVIDE([Total Revenue], [Active Technicians])` | $145,753 |

## Time intelligence

These shift with the date filter in the report. They rely on `dim_date` being
marked as the model's date table.

| Measure | DAX |
|---|---|
| Revenue MTD | `TOTALMTD([Total Revenue], dim_date[date])` |
| Revenue YTD | `TOTALYTD([Total Revenue], dim_date[date])` |
| Revenue Last Month | `CALCULATE([Total Revenue], DATEADD(dim_date[date], -1, MONTH))` |
| Revenue MoM % | `DIVIDE([Total Revenue] - [Revenue Last Month], [Revenue Last Month])` |

Revenue YTD for 2026 in the sample data is $1,962,850, which the harness checks.

## Cash and accounts receivable

| Measure | DAX | Value |
|---|---|---|
| Invoiced Amount | `SUM(fact_invoices[amount])` | $2,332,041 |
| Collected | `SUM(fact_invoices[paid_amount])` | $1,726,320 |
| Outstanding AR | `[Invoiced Amount] - [Collected]` | $605,721 |
| Collection Rate | `DIVIDE([Collected], [Invoiced Amount])` | 74.0% |

### A note on `dim_date` -> `fact_invoices`

`fact_invoices` carries its own `date_key`, and `dim_date` could join to it
directly. That relationship exists in the model (`rel_invoices_date`) but is
set **inactive**, because `fact_invoices` also reaches `dim_date` through the
`rel_invoices_job` bridge (`fact_invoices` -> `fact_jobs` -> `dim_date`). With
both paths active, a filter on `dim_date` would reach `fact_invoices` two ways
at once — the exact tie the Tabular engine rejects as an ambiguous filter
path. Only one path may be active at a time, and the bridge through
`fact_jobs` is the one kept live, consistent with treating the invoice-to-job
relationship as the model's fact-to-fact backbone. The direct path is also
redundant data, not a distinct grain: an invoice's `date_key` always equals
its job's `date_key` by construction (`data/generate.py` writes both fact rows
from the same loop date), so the two paths never disagree. A measure that
needed the direct relationship instead of the bridge would use
`USERELATIONSHIP('fact_invoices'[date_key], 'dim_date'[date_key])` inside
`CALCULATE`; none of the measures above need that today.
