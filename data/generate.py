"""Generate the star-schema CSVs for Cascade Field Services (synthetic).

Four dimensions and two facts, seeded so the data is identical on every run.
This is the data the Power BI semantic model sits on top of, and the data the
validation harness checks the DAX measures against.

    python data/generate.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 73
START = date(2025, 12, 1)
END = date(2026, 5, 31)
OUT = Path(__file__).resolve().parent

REGIONS = ["North", "South", "Metro"]
TEAMS = ["Install", "Service", "Maintenance"]
SERVICES = [
    ("AC Tune-Up", "Maintenance", 149),
    ("AC Repair", "Service", 320),
    ("Furnace Repair", "Service", 340),
    ("System Install", "Install", 6200),
    ("Duct Cleaning", "Maintenance", 410),
    ("Thermostat Install", "Service", 260),
    ("Emergency Call", "Service", 480),
]
SEGMENTS = ["Residential", "Commercial"]
FIRST = ["Avery", "Blake", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper",
         "Iris", "Jordan", "Kai", "Logan"]
LAST = ["Nolan", "Pierce", "Quint", "Reyes", "Sloan", "Tate", "Underwood", "Voss"]


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def date_key(d):
    return d.year * 10000 + d.month * 100 + d.day


def write(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    rng = random.Random(SEED)

    # dim_date
    months = ["", "January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    dim_date = [
        [date_key(d), d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month,
         months[d.month], d.isocalendar().week, d.weekday(), int(d.weekday() >= 5)]
        for d in daterange(START, END)
    ]

    # dim_technician
    techs = []
    used = set()
    for i in range(1, 17):
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if name not in used:
                used.add(name)
                break
        techs.append([i, name, rng.choice(REGIONS), rng.choice(TEAMS),
                      (START - timedelta(days=rng.randint(120, 1600))).isoformat()])

    # dim_service
    services = [[i + 1, s[0], s[1], s[2]] for i, s in enumerate(SERVICES)]

    # dim_customer
    customers = [
        [i, f"{rng.choice(FIRST)} {rng.choice(LAST)}"
         if (seg := rng.choices(SEGMENTS, weights=[70, 30])[0]) == "Residential"
         else f"{rng.choice(['Apex', 'Vertex', 'Summit', 'Harbor'])} "
              f"{rng.choice(['Foods', 'Realty', 'Logistics', 'Group'])}",
         seg, rng.choice(["Cascade", "Fairview", "Brookline", "Easton", "Westgate"])]
        for i in range(1, 401)
    ]

    # facts
    fact_jobs, fact_invoices = [], []
    job_key = inv_key = 0
    for d in daterange(START, END):
        season = 1.0 + 0.4 * (1 if d.month in (1, 2, 7, 8) else 0)  # winter/summer peaks
        n = max(0, int(rng.gauss(14 * season, 3))) if d.weekday() < 5 else int(rng.gauss(5, 2))
        for _ in range(max(0, n)):
            job_key += 1
            svc = rng.choice(services)
            tech = rng.choice(techs)
            cust = rng.choice(customers)
            status = rng.choices(["Completed", "Canceled", "Scheduled"],
                                 weights=[80, 8, 12])[0]
            ftf_prob = 0.74 if tech[3] != "Install" else 0.62
            ftf = int(status == "Completed" and rng.random() < ftf_prob)
            duration = int(rng.gauss(110 if svc[2] == "Maintenance" else 180, 35))
            revenue = round(svc[3] * rng.uniform(0.9, 1.2), 2) if status == "Completed" else 0.0
            cost = round(revenue * rng.uniform(0.45, 0.68), 2) if revenue else 0.0
            fact_jobs.append([job_key, date_key(d), tech[0], svc[0], cust[0],
                              status, ftf, max(30, duration), revenue, cost])
            if status == "Completed":
                inv_key += 1
                paid = revenue if rng.random() < 0.7 else round(revenue * rng.uniform(0, 0.5), 2)
                inv_status = "Paid" if paid >= revenue else ("Partial" if paid > 0 else "Open")
                fact_invoices.append([inv_key, date_key(d), job_key, revenue, paid, inv_status])

    write("dim_date.csv",
          ["date_key", "date", "year", "quarter", "month", "month_name",
           "week", "weekday", "is_weekend"], dim_date)
    write("dim_technician.csv",
          ["technician_key", "name", "region", "team", "hire_date"], techs)
    write("dim_service.csv",
          ["service_key", "service", "category", "list_price"], services)
    write("dim_customer.csv",
          ["customer_key", "name", "segment", "city"], customers)
    write("fact_jobs.csv",
          ["job_key", "date_key", "technician_key", "service_key", "customer_key",
           "status", "first_time_fix", "duration_min", "revenue", "cost"], fact_jobs)
    write("fact_invoices.csv",
          ["invoice_key", "date_key", "job_key", "amount", "paid_amount", "status"],
          fact_invoices)

    print(f"dim_date={len(dim_date)} technicians={len(techs)} services={len(services)} "
          f"customers={len(customers)} jobs={len(fact_jobs)} invoices={len(fact_invoices)}")


if __name__ == "__main__":
    main()
