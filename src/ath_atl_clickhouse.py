"""
ClickHouse-powered replacement for the ath-atl-finder agent.

Queries the `stock_analysis.prices` table for ATH and ATL per ticker
(including the exact date of each extreme), then writes the result to
src/data/pipeline/02_ath_atl.json — same schema the rest of the pipeline expects.

Prerequisites:
    - load_to_clickhouse.py must have been run first
    - pip install clickhouse-connect

Run:
    python3 src/ath_atl_clickhouse.py

Equivalent agent work replaced:
    The ath-atl-finder agent loops through each ticker's JSON file in Python,
    iterates all ~2,500 close prices, and tracks the max/min manually.
    This script does the same with a single SQL query across all tickers at once.

SQL used:
    SELECT
        ticker,
        max(close)           AS ath_price,
        argMax(date, close)  AS ath_date,   -- date where close was highest
        min(close)           AS atl_price,
        argMin(date, close)  AS atl_date    -- date where close was lowest
    FROM stock_analysis.prices
    GROUP BY ticker
    ORDER BY ticker

argMax/argMin are ClickHouse aggregate functions that return the value of
the first argument at the row where the second argument is at its max/min.
"""

import json
from pathlib import Path
import clickhouse_connect

OUTPUT_PATH = Path("src/data/pipeline/02_ath_atl.json")

QUERY = """
SELECT
    ticker,
    max(close)           AS ath_price,
    argMax(date, close)  AS ath_date,
    min(close)           AS atl_price,
    argMin(date, close)  AS atl_date
FROM stock_analysis.prices
GROUP BY ticker
ORDER BY ticker
"""


def main():
    client = clickhouse_connect.get_client(
    host="localhost",
    port=8123,
    username="default",
    password="mysecretpassword"
)

    result = client.query(QUERY)

    rows = []
    for ticker, ath_price, ath_date, atl_price, atl_date in result.result_rows:
        rows.append({
            "ticker":    ticker,
            "ath_price": round(float(ath_price), 2),
            "ath_date":  str(ath_date),
            "atl_price": round(float(atl_price), 2),
            "atl_date":  str(atl_date),
        })
        print(f"  {ticker:6s}  ATH {ath_price:.2f} on {ath_date}  |  ATL {atl_price:.2f} on {atl_date}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(rows, f, indent=2)

    print(f"\nWrote {len(rows)} tickers → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
