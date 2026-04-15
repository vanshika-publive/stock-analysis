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
