"""
Ingest all fetched ticker JSONs into ClickHouse.

Reads:  src/data/pipeline/01_fetcher/{TICKER}.json  (native yfinance chart format)
Writes: ClickHouse table `stock_analysis.prices`

Run once (or re-run to reload):
    source .venv/bin/activate
    pip install clickhouse-connect
    python3 src/load_to_clickhouse.py

ClickHouse must be running locally on port 8123 (default Docker setup):
    docker run -d --name clickhouse -p 8123:8123 -p 9000:9000 clickhouse/clickhouse-server
"""

import json
import datetime
from pathlib import Path
import clickhouse_connect

FETCHER_DIR = Path("src/data/pipeline/01_fetcher")
MANIFEST = FETCHER_DIR / "manifest.json"

CREATE_DB = "CREATE DATABASE IF NOT EXISTS stock_analysis"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS stock_analysis.prices (
    ticker      LowCardinality(String),
    date        Date,
    open        Float64,
    high        Float64,
    low         Float64,
    close       Float64,
    volume      UInt64
) ENGINE = MergeTree()
ORDER BY (ticker, date)
"""


def parse_ticker_json(path: Path) -> list[tuple]:
    """
    Extract (ticker, date, open, high, low, close, volume) rows
    from the native yfinance chart API JSON format.
    """
    with open(path) as f:
        raw = json.load(f)

    result = raw["chart"]["result"][0]
    ticker = result["meta"]["symbol"]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    opens   = quote.get("open",   [None] * len(timestamps))
    highs   = quote.get("high",   [None] * len(timestamps))
    lows    = quote.get("low",    [None] * len(timestamps))
    closes  = quote.get("close",  [None] * len(timestamps))
    volumes = quote.get("volume", [0]    * len(timestamps))

    rows = []
    for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, volumes):
        if c is None:
            continue  # skip bars with no close (market holiday gaps)
        date = datetime.date.fromtimestamp(ts)
        rows.append((
            ticker,
            date,
            float(o) if o is not None else 0.0,
            float(h) if h is not None else 0.0,
            float(l) if l is not None else 0.0,
            float(c),
            int(v)  if v is not None else 0,
        ))
    return rows


def main():
    with open(MANIFEST) as f:
        manifest = json.load(f)
    ticker_files = [Path(p) for p in manifest["files"]]

    client = clickhouse_connect.get_client(
    host="localhost",
    port=8123,
    username="default",
    password="mysecretpassword"
)
    client.command(CREATE_DB)
    client.command(CREATE_TABLE)

    # Clear existing data so re-runs are idempotent
    client.command("TRUNCATE TABLE IF EXISTS stock_analysis.prices")

    total_rows = 0
    for path in ticker_files:
        rows = parse_ticker_json(path)
        if not rows:
            print(f"  [skip] {path.name} — no rows parsed")
            continue

        client.insert(
            "stock_analysis.prices",
            rows,
            column_names=["ticker", "date", "open", "high", "low", "close", "volume"],
        )
        print(f"  [ok] {rows[0][0]:6s}  {len(rows):,} rows")
        total_rows += len(rows)

    print(f"\nDone. {total_rows:,} total rows inserted into stock_analysis.prices")


if __name__ == "__main__":
    main()
