# Stock Analysis — ATH/ATL Time Gap Pipeline

A multi-agent stock analysis system that fetches 10 years of daily price data for major tickers and analyzes the time gap between each stock's all-time low (ATL) and all-time high (ATH). Results are exported as a styled Excel workbook, a PowerPoint deck, and a PDF report.

> **Not investment advice.** All figures are sourced from Yahoo Finance daily bars (split-adjusted) and are for analytical/educational purposes only.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Tickers Covered](#tickers-covered)
- [Pipeline Overview](#pipeline-overview)
- [Project Structure](#project-structure)
- [Subagents](#subagents)
- [JSON Data Flow](#json-data-flow)
- [Hooks](#hooks)
- [Output Files](#output-files)
- [Setup & Installation](#setup--installation)
- [Running the Pipeline](#running-the-pipeline)
- [Configuration](#configuration)
- [API & Alternatives](#api--alternatives)
- [ClickHouse Integration](#clickhouse-integration)
- [Do Nots](#do-nots)
- [Current Results](#current-results)

---

## What It Does

The pipeline answers one core question per ticker:

> *How many days did it take this stock to go from its all-time low to its all-time high — and what does that say about its risk profile?*

It fetches 10 years of OHLCV data, finds the ATL and ATH within that window, computes the duration, assigns a speed label (`Rocket`, `Fast Mover`, `Steady Climber`) and a risk label (`Conservative`, `Moderate`, `Aggressive`, `Speculative`), and writes a human-readable analysis narrative for each ticker.

---

## Tickers Covered

| Ticker | Company | Risk Label | Speed Label | Days ATL→ATH |
|--------|---------|------------|-------------|-------------|
| AAPL | Apple | Conservative | Steady Climber | 3,492 |
| MSFT | Microsoft | Conservative | Steady Climber | 3,321 |
| AMZN | Amazon | Conservative | Steady Climber | 3,476 |
| GOOGL | Alphabet | Conservative | Steady Climber | 3,508 |
| SPY | S&P 500 ETF | Conservative | Steady Climber | 3,502 |
| AMD | AMD | Aggressive | Fast Mover | 3,478 |
| META | Meta | Aggressive | Rocket | 1,015 |
| TSLA | Tesla | Speculative | Rocket | 2,394 |
| NVDA | NVIDIA | Speculative | Rocket | 3,465 |
| COIN | Coinbase | Speculative | Rocket | 924 |

---

## Pipeline Overview

The pipeline runs 5 subagents in sequence. Each agent reads from the previous stage's JSON output and writes an enriched JSON to the next stage.

```
┌─────────────────────────────────────────────────────────┐
│  Input: ticker symbols (AAPL, TSLA, MSFT, …)            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ① stock-fetcher  (runs once per ticker × 10)           │
│  yfinance → Yahoo Finance API → 10y daily OHLCV         │
│  Writes: src/data/pipeline/01_fetcher/{TICKER}.json      │
│  Also:   src/data/pipeline/01_fetcher/manifest.json      │
└────────────────────────┬────────────────────────────────┘
                         │  🪝 PostToolUse:Write → hook_log.txt
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ② ath-atl-finder  (aggregate, runs once)               │
│  Scans all 10 cached JSONs → finds ATH + ATL per ticker  │
│  Writes: src/data/pipeline/02_ath_atl.json               │
└────────────────────────┬────────────────────────────────┘
                         │  🪝 PostToolUse:Write → hook_log.txt
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ③ time-delta-calculator                                │
│  Computes days between ATL→ATH, assigns speed label      │
│  Writes: src/data/pipeline/03_time_delta.json            │
└────────────────────────┬────────────────────────────────┘
                         │  🪝 PostToolUse:Write → hook_log.txt
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ④ stock-analyst                                        │
│  Writes risk_label + analysis narrative per ticker       │
│  Writes: src/data/pipeline/04_aggregated_staged.json     │
└────────────────────────┬────────────────────────────────┘
                         │  🪝 PostToolUse:Write + SubagentStop hooks
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ⑤ aggregator                                           │
│  Final consolidation → canonical output file             │
│  Writes: src/outputs/aggregated.json                     │
└────────────────────────┬────────────────────────────────┘
                         │  🪝 Stop hook → verifies aggregated.json
                         ▼
┌─────────────────┬──────────────────┬────────────────────┐
│  xlsx skill     │  pptx skill      │  pdf skill          │
│  stock_report   │  stock_deck      │  stock_report       │
│  .xlsx          │  .pptx           │  .pdf               │
└─────────────────┴──────────────────┴────────────────────┘
```

---

## Project Structure

```
stock-analysis/
├── CLAUDE.md                          # Pipeline instructions for the AI
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
│
├── .claude/
│   ├── agents/                        # Subagent definition files
│   │   ├── fetcher.md
│   │   ├── ath-atl.md
│   │   ├── time-delta.md
│   │   ├── analyst.md
│   │   └── aggregator.md
│   ├── skills/
│   │   └── generate-report/
│   │       └── SKILL.md              # Skill instructions for report generation
│   ├── settings.json                  # Hook definitions (PreToolUse, PostToolUse, Stop, SubagentStop)
│   └── settings.local.json            # Network permissions (WebFetch whitelist)
│
└── src/
    ├── orchestrator.py                # Pipeline orchestration entry point
    ├── generate_report.py             # Excel report generator (openpyxl)
    ├── generate_pptx.py               # PowerPoint deck generator
    ├── generate_pdf.py                # PDF report generator
    │
    ├── data/
    │   ├── hook_log.txt               # Auto-generated write audit log (from hooks)
    │   └── pipeline/
    │       ├── 01_fetcher/
    │       │   ├── AAPL.json          # Raw yfinance response (~133–282 KB each)
    │       │   ├── TSLA.json
    │       │   ├── MSFT.json
    │       │   ├── NVDA.json
    │       │   ├── AMZN.json
    │       │   ├── META.json
    │       │   ├── GOOGL.json
    │       │   ├── SPY.json
    │       │   ├── COIN.json
    │       │   ├── AMD.json
    │       │   └── manifest.json      # List of all fetched tickers + file paths
    │       ├── 02_ath_atl.json        # ATH + ATL price/date per ticker
    │       ├── 03_time_delta.json     # + days_between + speed_label
    │       └── 04_aggregated_staged.json  # + risk_label + analysis
    │
    └── outputs/
        ├── aggregated.json            # Master output (consumed by all skills)
        ├── stock_report.xlsx          # Styled Excel workbook
        ├── stock_deck.pptx            # PowerPoint presentation
        └── stock_report.pdf           # PDF report
```

---

## Subagents

All subagents are defined in `.claude/agents/`. Each is an independent unit that reads from the prior stage's JSON and writes to the next.

### ① `stock-fetcher`

**Role:** Data ingestion layer — one run per ticker.

- **Input:** Ticker symbol (e.g. `AAPL`)
- **API:** `yfinance` → `query1.finance.yahoo.com` (whitelisted in `settings.local.json`)
- **Range:** 10 years of daily OHLCV data (`10y / 1d`)
- **Bars:** ~2,513 per ticker
- **Output:** `src/data/pipeline/01_fetcher/{TICKER}.json`
- **Cache:** If a ticker's JSON already exists, it is not re-fetched
- **Also writes:** `manifest.json` — a registry of all fetched tickers
- **Libraries:** `yfinance`, `pandas`
- **Production alternative:** Switch to Polygon.io (requires API key)

Each output JSON follows the native yfinance schema:

```json
{
  "chart": {
    "result": [{
      "meta": { "symbol": "AAPL", "currency": "USD", "longName": "Apple Inc.", ... },
      "timestamp": [1462320000, 1462406400, ...],
      "indicators": {
        "quote": [{ "open": [...], "high": [...], "low": [...], "close": [...], "volume": [...] }],
        "adjclose": [{ "adjclose": [...] }]
      }
    }]
  }
}
```

---

### ② `ath-atl-finder`

**Role:** Reads all 10 cached JSONs and extracts the all-time high and all-time low from each.

- **Input:** `src/data/pipeline/01_fetcher/*.json`
- **Logic:** `max(close[])` → ATH, `min(close[])` → ATL
- **Output:** `src/data/pipeline/02_ath_atl.json`

```json
[
  { "ticker": "AAPL", "ath_price": 288.62, "ath_date": "2025-12-03", "atl_price": 22.37, "atl_date": "2016-05-12" },
  ...
]
```

---

### ③ `time-delta-calculator`

**Role:** Computes days between ATL and ATH and assigns a speed label.

- **Input:** `src/data/pipeline/02_ath_atl.json`
- **Output:** `src/data/pipeline/03_time_delta.json`
- **Adds:** `days_between` (int), `speed_label` (enum)

**Speed label thresholds:**

| Label | Days ATL → ATH |
|-------|----------------|
| `Rocket` | < 1,500 days |
| `Fast Mover` | 1,500 – 2,500 days |
| `Steady Climber` | > 2,500 days |

---

### ④ `stock-analyst`

**Role:** Writes a human-readable analysis narrative and assigns a risk label per ticker.

- **Input:** `src/data/pipeline/03_time_delta.json`
- **Output:** `src/data/pipeline/04_aggregated_staged.json`
- **Adds:** `risk_label` (enum), `analysis` (string with disclaimer)

**Risk label criteria:**

| Label | Description | Examples |
|-------|-------------|---------|
| `Conservative` | Slow, steady multi-year growth | AAPL, MSFT, AMZN, GOOGL, SPY |
| `Moderate` | Balanced growth and volatility | — |
| `Aggressive` | Higher volatility, faster moves | META, AMD |
| `Speculative` | Extreme gains, extreme risk | TSLA, NVDA, COIN |

**Example output object:**

```json
{
  "ticker": "NVDA",
  "ath_price": 212.19,
  "ath_date": "2025-10-29",
  "atl_price": 0.86,
  "atl_date": "2016-05-04",
  "days_between": 3465,
  "speed_label": "Rocket",
  "risk_label": "Speculative",
  "analysis": "NVDA: move from ATL to ATH is ~246.7x over 3465 days (Rocket). ATH 2025-10-29 vs ATL 2016-05-04. Figures from Yahoo daily bars (split-adjusted); not investment advice."
}
```

---

### ⑤ `aggregator`

**Role:** Final consolidation — copies staged data to the canonical output folder.

- **Input:** `src/data/pipeline/04_aggregated_staged.json`
- **Output:** `src/outputs/aggregated.json`
- **Schema change:** None. This is a pure consolidation step.
- **Consumed by:** `generate_report.py`, `generate_pptx.py`, `generate_pdf.py`, and all output skills.

---

## JSON Data Flow

Each pipeline stage enriches the JSON objects with new fields. The table below shows exactly which fields are added at each stage:

| Field | Added at Stage | Type | Description |
|-------|----------------|------|-------------|
| `ticker` | Stage 1 (meta) | string | Stock symbol |
| `ath_price` | Stage 2 | float | All-time high closing price (10y window) |
| `ath_date` | Stage 2 | string (ISO 8601) | Date of ATH |
| `atl_price` | Stage 2 | float | All-time low closing price (10y window) |
| `atl_date` | Stage 2 | string (ISO 8601) | Date of ATL |
| `days_between` | Stage 3 | int | Calendar days from ATL to ATH |
| `speed_label` | Stage 3 | enum string | `Rocket` / `Fast Mover` / `Steady Climber` |
| `risk_label` | Stage 4 | enum string | `Conservative` / `Moderate` / `Aggressive` / `Speculative` |
| `analysis` | Stage 4 | string | Human-readable narrative with disclaimer |

Raw yfinance data fields (stage 1 only — ~2,513 bars per ticker):

| Field path | Description |
|-----------|-------------|
| `chart.result[0].meta.*` | Symbol, currency, exchange, 52-week range, etc. |
| `chart.result[0].timestamp[]` | Unix timestamps for each trading day |
| `chart.result[0].indicators.quote[0].close[]` | Daily closing prices — used for ATH/ATL |
| `chart.result[0].indicators.adjclose[0].adjclose[]` | Split-adjusted close prices |

---

## Hooks

All hooks are defined in `.claude/settings.json`. They fire automatically at runtime without any manual invocation.

### `PreToolUse` — Security Guard

**Trigger:** Before any `Bash` tool call.

**What it does:** Scans the bash command string for dangerous patterns. Exits with code `1` to block the command entirely if matched.

**Blocked patterns:** `rm -rf` · `DROP TABLE` · `sudo rm`

```python
# Simplified logic
blocked = ['rm -rf', 'DROP TABLE', 'sudo rm']
if any(x in cmd for x in blocked):
    sys.exit(1)  # blocks the tool call
```

---

### `PostToolUse` — Write Audit Log

**Trigger:** After every `Write` tool call by any agent.

**What it does:** Appends a timestamped line to `src/data/hook_log.txt`.

```bash
echo "[hook] File written at $(date)" >> src/data/hook_log.txt
```

**Result:** A passive audit trail of every JSON file written. The last full pipeline run produced 18 entries — one per file write across all stages.

---

### `Stop` — Pipeline Completion Verifier

**Trigger:** When the entire Claude run completes.

**What it does:** Checks whether `src/outputs/aggregated.json` exists. Prints a success message or a warning accordingly.

```
[Stop hook] Run complete. Outputs in src/outputs/   ✓
[Stop hook] Warning: aggregated.json not found       ✗
```

This acts as a final gate — if the aggregator fails silently, this hook surfaces the failure before broken output reaches the Excel/PDF/PPTX skills.

---

### `SubagentStop` — Subagent Progress Logger

**Trigger:** When any subagent finishes execution.

**What it does:** Reads the `agent_type` from stdin and echoes it as a breadcrumb log.

```bash
python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"[hook] Subagent done: {d.get('agent_type','unknown')}\")
" 2>/dev/null || true
```

The `|| true` ensures a malformed stdin never crashes the pipeline.

---

## Output Files

### `src/outputs/aggregated.json`

The master data file containing all 10 tickers with all enriched fields. This is the canonical source consumed by every output skill.

### `src/outputs/stock_report.xlsx`

Generated by `src/generate_report.py` using `openpyxl`.

**Features:**
- 9-column layout: Ticker, ATH Price, ATH Date, ATL Price, ATL Date, Days Between, Speed Label, Risk Label, Analysis
- Dark blue header row (`#1F3864`) with white bold text
- Risk label cells are color-coded:
  - `Conservative` → Green (`#92D050`)
  - `Moderate` → Yellow (`#FFFF00`)
  - `Aggressive` → Orange (`#FF6600`)
  - `Speculative` → Red (`#FF0000`)
- Alternating light gray row shading
- Frozen header row (row 1)
- Auto-filter enabled on all columns
- Optimized column widths per field

### `src/outputs/stock_deck.pptx`

Generated by `src/generate_pptx.py` using `python-pptx`. One slide per ticker, showing ATH/ATL details, days between, speed label, risk label, and analysis text.

### `src/outputs/stock_report.pdf`

Generated by `src/generate_pdf.py`. A printable/shareable version of the final report.

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- Docker (optional, for local MCP servers)
- Claude Desktop or Claude Code

### 1. Clone and enter the repo

```bash
git clone <repo-url>
cd stock-analysis
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
.venv\Scripts\activate          # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install openpyxl python-pptx  # for report generation scripts
```

`requirements.txt` contents:

```
yfinance
pandas
clickhouse-connect
```

### 4. Verify the `.claude/settings.local.json` network permission

The fetcher agent needs access to Yahoo Finance. Confirm this file exists and contains:

```json
{
  "permissions": {
    "allow": [
      "WebFetch(domain:query1.finance.yahoo.com)"
    ]
  }
}
```

---

## Running the Pipeline

### Full pipeline (all 5 subagents in order)

Open the project in Claude Desktop or Claude Code and run:

```
Run the full stock analysis pipeline for all tickers.
```

The AI will execute subagents in order: fetcher (×10) → ath-atl-finder → time-delta-calculator → stock-analyst → aggregator.

### Generate output files after aggregation

```
Generate the Excel report from aggregated.json.
Generate the PowerPoint deck from aggregated.json.
Generate the PDF report from aggregated.json.
```

Or run the scripts directly:

```bash
python3 src/generate_report.py    # → src/outputs/stock_report.xlsx
python3 src/generate_pptx.py      # → src/outputs/stock_deck.pptx
python3 src/generate_pdf.py       # → src/outputs/stock_report.pdf
```

### Re-run a single stage

Because each stage writes to a separate JSON file, you can re-run any individual agent without re-running the full pipeline. For example, to regenerate the analysis with a different prompt:

```
Re-run the stock-analyst agent on src/data/pipeline/03_time_delta.json.
```

### Add a new ticker

```
Add AMZN to the pipeline: run the fetcher for AMZN, then re-run ath-atl-finder onward.
```

---

## Configuration

### `.claude/settings.json` — Hook definitions

Controls all 4 lifecycle hooks (see [Hooks](#hooks) section). Modify here to add logging, alerting, or additional safety guards.

### `.claude/settings.local.json` — Network permissions

Controls which external domains the fetcher agent can reach. Currently whitelisted:

```
query1.finance.yahoo.com   (Yahoo Finance / yfinance API)
```

To switch to Polygon.io in production, add:

```json
{
  "permissions": {
    "allow": [
      "WebFetch(domain:api.polygon.io)"
    ]
  }
}
```

### `.claude/agents/*.md` — Subagent definitions

Each `.md` file is the system prompt / instruction set for its corresponding subagent. Edit these to change how an agent behaves — e.g. to alter the speed label thresholds or the risk classification logic.

---

## API & Alternatives

### Current: `yfinance` (Yahoo Finance)

- **Cost:** Free, no API key required
- **Rate limits:** Managed automatically by yfinance with retries
- **Granularity:** Daily bars only (no intraday)
- **Stability:** Unofficial API — subject to change without notice
- **Best for:** Development, research, small-scale runs

### Production alternative: Polygon.io

- **Cost:** Paid (free tier available)
- **Reliability:** Official REST API with SLA
- **Granularity:** Tick, minute, hour, day
- **Auth:** Requires `POLYGON_API_KEY` environment variable (never hardcode)
- **Switch:** Update the fetcher agent's `.md` file and add Polygon's domain to `settings.local.json`

### Other alternatives

| Provider | Free Tier | Key Required | Notes |
|----------|-----------|--------------|-------|
| Alpha Vantage | Yes (25 req/day) | Yes | Good for fundamentals too |
| Tiingo | Yes | Yes | Clean REST, reliable |
| EOD Historical Data | No | Yes | Global coverage |
| Financial Modeling Prep | Yes (limited) | Yes | Fundamentals + prices |

---

## ClickHouse Integration

This section describes the experimental ClickHouse layer added to the project for learning and experimentation. It replaces the JSON-scanning approach of the `ath-atl-finder` agent with a single SQL query against a columnar database, and lays the groundwork for more advanced time-series analytics.

### Why ClickHouse?

The `ath-atl-finder` agent currently works by reading 10 separate JSON files and iterating over ~2,500 closing prices per ticker in Python to find the max and min. This works fine at 10 tickers. But ClickHouse is a columnar OLAP database built specifically for aggregate queries over large time-series datasets — finding a max/min across millions of rows is exactly what it is optimized for.

Beyond ATH/ATL, having all OHLCV bars in ClickHouse unlocks queries the current pipeline cannot do at all: rolling 52-week highs, moving averages, drawdown windows, cross-ticker correlation — all expressible as SQL without touching Python or JSON files.

### Architecture: what changes

The original pipeline reads and writes flat JSON files at every stage. The ClickHouse integration adds a parallel data path where raw OHLCV bars live in a database table instead. Stage 2 (ATH/ATL) is replaced by a SQL query; everything downstream (stages 3–5) remains unchanged because the output written to `02_ath_atl.json` is identical in schema.

```
Original path:
  01_fetcher/*.json  →  [Python loop, ~25k iterations]  →  02_ath_atl.json

ClickHouse path:
  01_fetcher/*.json  →  load_to_clickhouse.py  →  stock_analysis.prices (CH table)
                                                          │
                                              ath_atl_clickhouse.py (1 SQL query)
                                                          │
                                                   02_ath_atl.json  (same schema)
```

Stages 3, 4, 5, and all output scripts are unaffected — they still read from `02_ath_atl.json` onward.

### ClickHouse table schema

```sql
CREATE TABLE stock_analysis.prices (
    ticker      LowCardinality(String),  -- low-cardinality: only ~10 distinct values
    date        Date,
    open        Float64,
    high        Float64,
    low         Float64,
    close       Float64,
    volume      UInt64
) ENGINE = MergeTree()
ORDER BY (ticker, date)
```

**Design notes:**

- **`MergeTree` engine** is ClickHouse's standard table engine for time-series. It stores data sorted by the `ORDER BY` key on disk, making range scans by `(ticker, date)` extremely fast.
- **`LowCardinality(String)`** for `ticker` tells ClickHouse that this column has very few distinct values (~10). It stores it as a dictionary-encoded column internally, which reduces memory and speeds up `GROUP BY ticker` queries significantly.
- **`ORDER BY (ticker, date)`** sorts rows first by ticker, then by date within each ticker. This means all of AAPL's rows are physically co-located on disk, so a `WHERE ticker = 'AAPL'` scan reads a contiguous block — no scattered I/O.

### New files

#### `src/load_to_clickhouse.py`

Reads all 10 ticker JSONs from `src/data/pipeline/01_fetcher/` via `manifest.json`, parses the nested yfinance chart API format, and bulk-inserts all rows into ClickHouse.

**JSON parsing:** The yfinance chart API stores data as parallel arrays — a `timestamp[]` array of Unix timestamps and a `quote[0].close[]` array of prices at matching indices. The loader zips these arrays together, converts each Unix timestamp to a `datetime.date`, and skips any bar where `close` is `None` (these are market holiday gaps that yfinance includes as null entries).

```python
# Core parsing logic
for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, volumes):
    if c is None:
        continue  # skip null bars (market holiday gaps)
    date = datetime.date.fromtimestamp(ts)
    rows.append((ticker, date, float(o), float(h), float(l), float(c), int(v)))
```

**Idempotency:** The script runs `TRUNCATE TABLE` before inserting, so re-running it always produces a clean, consistent state. Safe to run multiple times.

**Expected output:**

```
  [ok] AAPL    2513 rows
  [ok] TSLA    1706 rows
  [ok] MSFT    2515 rows
  [ok] NVDA    2515 rows
  [ok] AMZN    2515 rows
  [ok] META    3272 rows
  [ok] GOOGL   2515 rows
  [ok] SPY     2516 rows
  [ok] COIN    1030 rows
  [ok] AMD     2515 rows

Done. 24,612 total rows inserted into stock_analysis.prices
```

#### `src/ath_atl_clickhouse.py`

Runs a single SQL query against `stock_analysis.prices` to find ATH and ATL (price + date) for all tickers simultaneously, then writes the result to `src/data/pipeline/02_ath_atl.json` in exactly the same schema that stage 3 (`time-delta-calculator`) expects.

### The SQL query explained

```sql
SELECT
    ticker,
    max(close)           AS ath_price,
    argMax(date, close)  AS ath_date,
    min(close)           AS atl_price,
    argMin(date, close)  AS atl_date
FROM stock_analysis.prices
GROUP BY ticker
ORDER BY ticker
```

The naive `max(close)` / `min(close)` gives the prices but not the dates. ClickHouse's `argMax(X, Y)` aggregate function solves this: it returns the value of `X` at the row where `Y` is at its maximum. So `argMax(date, close)` returns the date of the highest closing price — exactly what the pipeline needs.

| Function | What it returns |
|---|---|
| `max(close)` | The highest closing price across all rows for the ticker |
| `argMax(date, close)` | The date on which that highest close occurred |
| `min(close)` | The lowest closing price |
| `argMin(date, close)` | The date on which that lowest close occurred |

This single query replaces ~25,000 Python iterations across 10 JSON files (one pass per ticker, ~2,500 rows each). ClickHouse executes it as a columnar scan — reading only the `ticker`, `date`, and `close` columns from disk, skipping `open`, `high`, `low`, `volume` entirely.

### Output schema

The output written to `02_ath_atl.json` is identical to what the original `ath-atl-finder` agent produces:

```json
[
  {
    "ticker":    "AAPL",
    "ath_price": 288.62,
    "ath_date":  "2025-12-03",
    "atl_price": 22.37,
    "atl_date":  "2016-05-12"
  },
  ...
]
```

Because the schema is unchanged, `time-delta-calculator` (stage 3), `stock-analyst` (stage 4), `aggregator` (stage 5), and all output scripts work without any modification.

### Setup and running

#### 1. Start ClickHouse locally via Docker

```bash
docker run -d \
  --name clickhouse \
  -p 8123:8123 \
  -p 9000:9000 \
  clickhouse/clickhouse-server
```

Port `8123` is the HTTP interface used by `clickhouse-connect`. Port `9000` is the native TCP interface (used by the `clickhouse-client` CLI).

Verify it is running:

```bash
curl http://localhost:8123/ping
# → Ok.
```

#### 2. Install the Python client

```bash
pip install clickhouse-connect
# or: pip install -r requirements.txt  (already included)
```

`clickhouse-connect` is the official Python client maintained by ClickHouse, Inc. It uses the HTTP interface and supports both synchronous queries and bulk inserts.

#### 3. Load all ticker data into ClickHouse

```bash
python3 src/load_to_clickhouse.py
```

This creates the `stock_analysis` database and `prices` table if they do not exist, then inserts all rows from the 10 cached JSON files. Re-running is safe — it truncates before inserting.

#### 4. Run the ClickHouse-powered ATH/ATL finder

```bash
python3 src/ath_atl_clickhouse.py
```

This overwrites `src/data/pipeline/02_ath_atl.json` with results from the SQL query. From this point, the rest of the pipeline continues normally — run `time-delta-calculator`, `stock-analyst`, and `aggregator` as usual.

#### 5. (Optional) Explore the data interactively

Connect to ClickHouse with the CLI to run queries directly:

```bash
docker exec -it clickhouse clickhouse-client
```

```sql
-- Row count per ticker
SELECT ticker, count() AS bars
FROM stock_analysis.prices
GROUP BY ticker
ORDER BY bars DESC;

-- ATH and ATL for all tickers in one query
SELECT
    ticker,
    max(close) AS ath,
    argMax(date, close) AS ath_date,
    min(close) AS atl,
    argMin(date, close) AS atl_date,
    round(max(close) / min(close), 1) AS gain_multiple
FROM stock_analysis.prices
GROUP BY ticker
ORDER BY gain_multiple DESC;

-- Best single-day close gains per ticker
SELECT
    ticker,
    date,
    close,
    neighbor(close, -1) OVER (PARTITION BY ticker ORDER BY date) AS prev_close,
    round((close - prev_close) / prev_close * 100, 2) AS pct_change
FROM stock_analysis.prices
ORDER BY pct_change DESC
LIMIT 20;
```

### Dependency on cached data

`load_to_clickhouse.py` reads from `src/data/pipeline/01_fetcher/*.json` — the same files written by the `stock-fetcher` agent. The fetcher must have run at least once before loading into ClickHouse. If you add a new ticker to the pipeline, re-run the fetcher for that ticker and then re-run `load_to_clickhouse.py` to sync it into ClickHouse.

### `requirements.txt`

`clickhouse-connect` has been added to `requirements.txt`. Install all dependencies with:

```bash
pip install -r requirements.txt
pip install openpyxl python-pptx  # for report generation scripts
```

---

## Do Nots

Per `CLAUDE.md` — these rules are enforced by the `PreToolUse` hook:

- **Do not** delete files in `src/data/` — these are cached API results that save re-fetching costs
- **Do not** run `rm -rf` anywhere (blocked by hook)
- **Do not** hardcode API keys — use environment variables or `settings.local.json`
- **Do not** run `DROP TABLE` or destructive database commands (blocked by hook)

---

## Current Results

Results from the last full pipeline run (data as of April 2026, 10-year window):

| Ticker | ATL Price | ATL Date | ATH Price | ATH Date | Days | Speed | Risk | Gain |
|--------|-----------|----------|-----------|----------|------|-------|------|------|
| AAPL | $22.37 | 2016-05-12 | $288.62 | 2025-12-03 | 3,492 | Steady Climber | Conservative | ~12.9× |
| TSLA | $11.80 | 2019-06-03 | $498.83 | 2025-12-22 | 2,394 | Rocket | Speculative | ~42.3× |
| MSFT | $48.04 | 2016-06-27 | $555.45 | 2025-07-31 | 3,321 | Steady Climber | Conservative | ~11.6× |
| NVDA | $0.86 | 2016-05-04 | $212.19 | 2025-10-29 | 3,465 | Rocket | Speculative | ~246.7× |
| AMZN | $29.96 | 2016-04-28 | $258.60 | 2025-11-03 | 3,476 | Steady Climber | Conservative | ~8.6× |
| META | $88.09 | 2022-11-04 | $796.25 | 2025-08-15 | 1,015 | Rocket | Aggressive | ~9.0× |
| GOOGL | $33.63 | 2016-06-27 | $349.00 | 2026-02-03 | 3,508 | Steady Climber | Conservative | ~10.4× |
| SPY | $198.65 | 2016-06-27 | $697.84 | 2026-01-28 | 3,502 | Steady Climber | Conservative | ~3.5× |
| COIN | $31.55 | 2023-01-06 | $444.65 | 2025-07-18 | 924 | Rocket | Speculative | ~14.1× |
| AMD | $2.60 | 2016-04-21 | $267.08 | 2025-10-29 | 3,478 | Fast Mover | Aggressive | ~102.7× |

> All prices are split-adjusted daily closing prices from Yahoo Finance. Not investment advice.

---

## Visualizations

Two interactive HTML visualizations are included in the project root:

- **`pipeline_viz.html`** — Interactive agent pipeline diagram, JSON data flow map, and hook execution explorer (3 tabs)
- **`github_mcp_guide.html`** — Step-by-step guide to GitHub's MCP server integration

Open either file in a browser to explore.

---

*Last updated: April 2026*
