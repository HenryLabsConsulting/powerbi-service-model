"""Tests that lock in the measure logic and the star-schema integrity."""

import math

import duckdb
import pytest
from measures import connect, measures, revenue_ytd

# Expected values for the committed, seeded data set. A change to a measure's
# logic that moves any of these fails CI.
EXPECTED = {
    "total_revenue": 2332041.18,
    "total_cost": 1320493.81,
    "gross_margin": 1011547.37,
    "gross_margin_pct": 0.4338,
    "job_count": 2274,
    "completed_jobs": 1840,
    "canceled_jobs": 187,
    "cancellation_rate": 0.0822,
    "average_ticket": 1267.41,
    "first_time_fix_rate": 0.7033,
    "average_job_duration": 159.7,
    "active_technicians": 16,
    "revenue_per_technician": 145752.57,
    "invoiced_amount": 2332041.18,
    "collected": 1726320.04,
    "outstanding_ar": 605721.14,
    "collection_rate": 0.7403,
    "avg_monthly_revenue": 388673.53,
}


@pytest.fixture(scope="module")
def con():
    return connect()


@pytest.fixture(scope="module")
def m(con):
    return measures(con)


@pytest.mark.parametrize("key,expected", EXPECTED.items())
def test_measure_value(m, key, expected):
    assert math.isclose(m[key], expected, rel_tol=1e-4, abs_tol=0.05), \
        f"{key}: got {m[key]}, expected {expected}"


def test_internal_consistency(m):
    # Gross margin must equal revenue minus cost.
    assert math.isclose(m["gross_margin"], m["total_revenue"] - m["total_cost"], abs_tol=0.05)
    # Outstanding AR must equal invoiced minus collected.
    assert math.isclose(m["outstanding_ar"], m["invoiced_amount"] - m["collected"], abs_tol=0.05)
    # Completed plus canceled cannot exceed the total job count.
    assert m["completed_jobs"] + m["canceled_jobs"] <= m["job_count"]


def test_ytd_matches_filtered_year(con):
    assert math.isclose(revenue_ytd(con, 2026), 1962849.83, rel_tol=1e-4, abs_tol=0.05)
    assert revenue_ytd(con, 1999) == 0.0


def test_ratio_measures_guard_against_zero_denominator():
    # Mirrors the DAX DIVIDE behavior: an empty fact table has no completed jobs
    # and no active technicians, so the ratio measures must return 0.0 rather
    # than raise ZeroDivisionError.
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE fact_jobs (revenue DECIMAL, cost DECIMAL, status VARCHAR, "
        "first_time_fix INTEGER, technician_key INTEGER, duration_min INTEGER)"
    )
    con.execute("CREATE TABLE fact_invoices (amount DECIMAL, paid_amount DECIMAL)")

    m = measures(con)

    assert m["average_ticket"] == 0.0
    assert m["revenue_per_technician"] == 0.0
    assert m["gross_margin_pct"] == 0.0
    assert m["cancellation_rate"] == 0.0
    assert m["first_time_fix_rate"] == 0.0
    assert m["collection_rate"] == 0.0


def test_every_fact_row_resolves_to_a_dimension(con):
    orphan_jobs = con.execute("""
        SELECT COUNT(*) FROM fact_jobs j
        LEFT JOIN dim_date d ON d.date_key = j.date_key
        LEFT JOIN dim_technician t ON t.technician_key = j.technician_key
        LEFT JOIN dim_service s ON s.service_key = j.service_key
        LEFT JOIN dim_customer c ON c.customer_key = j.customer_key
        WHERE d.date_key IS NULL OR t.technician_key IS NULL
           OR s.service_key IS NULL OR c.customer_key IS NULL
    """).fetchone()[0]
    assert orphan_jobs == 0

    orphan_invoices = con.execute("""
        SELECT COUNT(*) FROM fact_invoices i
        LEFT JOIN fact_jobs j ON j.job_key = i.job_key
        WHERE j.job_key IS NULL
    """).fetchone()[0]
    assert orphan_invoices == 0
