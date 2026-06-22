"""Validation harness.

Power BI computes the DAX measures. To prove the logic is correct without
opening Power BI, each headline measure is re-implemented here in SQL and run
against the same star-schema data with DuckDB. The test module asserts the
numbers, so a change that breaks a measure's logic fails CI.

This is the bridge between "the model looks right" and "the model is right."
"""

from pathlib import Path

import duckdb

DATA = Path(__file__).resolve().parent.parent / "data"

TABLES = ["dim_date", "dim_technician", "dim_service",
          "dim_customer", "fact_jobs", "fact_invoices"]


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for t in TABLES:
        con.execute(
            f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('{(DATA / (t + '.csv')).as_posix()}', header=true)"
        )
    return con


def measures(con: duckdb.DuckDBPyConnection) -> dict:
    """Compute the headline measures, mirroring the DAX in model.tmdl."""
    jobs = con.execute("""
        SELECT
            ROUND(COALESCE(SUM(revenue), 0), 2)                                 AS total_revenue,
            ROUND(COALESCE(SUM(cost), 0), 2)                                    AS total_cost,
            COUNT(*)                                                            AS job_count,
            COUNT(*) FILTER (WHERE status = 'Completed')                        AS completed_jobs,
            COUNT(*) FILTER (WHERE status = 'Canceled')                         AS canceled_jobs,
            COUNT(*) FILTER (WHERE status = 'Completed' AND first_time_fix = 1) AS ftf_jobs,
            COUNT(DISTINCT technician_key)                                      AS active_technicians,
            ROUND(AVG(duration_min), 1)                                         AS avg_duration
        FROM fact_jobs
    """).fetchone()
    (total_revenue, total_cost, job_count, completed, canceled, ftf, techs, avg_dur) = jobs

    inv = con.execute("""
        SELECT ROUND(COALESCE(SUM(amount), 0), 2), ROUND(COALESCE(SUM(paid_amount), 0), 2)
        FROM fact_invoices
    """).fetchone()
    invoiced, collected = inv

    def div(a, b):
        # Mirrors DAX DIVIDE: a zero (or missing) denominator yields 0.0, never
        # a divide-by-zero. Every ratio measure routes through this guard.
        return round(a / b, 4) if b else 0.0

    gross_margin = round(total_revenue - total_cost, 2)
    return {
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "gross_margin": gross_margin,
        "gross_margin_pct": div(gross_margin, total_revenue),
        "job_count": job_count,
        "completed_jobs": completed,
        "canceled_jobs": canceled,
        "cancellation_rate": div(canceled, job_count),
        "average_ticket": div(total_revenue, completed),
        "first_time_fix_rate": div(ftf, completed),
        "average_job_duration": avg_dur,
        "active_technicians": techs,
        "revenue_per_technician": div(total_revenue, techs),
        "invoiced_amount": invoiced,
        "collected": collected,
        "outstanding_ar": round(invoiced - collected, 2),
        "collection_rate": div(collected, invoiced),
    }


def revenue_ytd(con: duckdb.DuckDBPyConnection, year: int) -> float:
    """Mirror of Revenue YTD for a given calendar year."""
    row = con.execute("""
        SELECT ROUND(SUM(j.revenue), 2)
        FROM fact_jobs j JOIN dim_date d ON d.date_key = j.date_key
        WHERE d.year = ?
    """, [year]).fetchone()
    return row[0] or 0.0


if __name__ == "__main__":
    con = connect()
    for name, value in measures(con).items():
        print(f"{name:<24} {value}")
    print(f"{'revenue_ytd_2026':<24} {revenue_ytd(con, 2026)}")
