# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Analyzes stocks by computing the time gap between their all-time low (ATL) and all-time high (ATH) within a 10-year window, then classifying them by speed and risk profile. Results are exported as Excel, PowerPoint, and PDF.

## Running the pipeline

The primary way to run the full pipeline is via natural language in Claude Code:

```
Run the full stock analysis pipeline for all tickers.
```

To run output generation scripts directly:

```bash
source .venv/bin/activate
python3 src/generate_report.py    # → src/outputs/stock_report.xlsx
python3 src/generate_pptx.py      # → src/outputs/stock_deck.pptx
python3 src/generate_pdf.py       # → src/outputs/stock_report.pdf
```

To run the orchestrator directly (Python-only path, no Claude subagents):

```bash
python3 src/orchestrator.py
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install openpyxl python-pptx  # required for output generation scripts
```

## Architecture

The pipeline has two execution modes:

1. **Claude subagent mode** (primary): The orchestrator in Claude Code launches 5 specialized subagents in order, each reading/writing a pipeline stage JSON file. Subagents are defined in `.claude/agents/*.md`.

2. **Python orchestrator mode** (`src/orchestrator.py`): Calls `claude` CLI via `subprocess` to invoke subagents programmatically. Note: `TICKERS` in `orchestrator.py` only lists 5 tickers, while the full pipeline covers 10.

### Pipeline stages and data files

Each stage writes a JSON file consumed by the next:

| Stage | Agent | Reads | Writes |
|-------|-------|-------|--------|
| 1 | `stock-fetcher` (×1 per ticker) | yfinance API | `src/data/pipeline/01_fetcher/{TICKER}.json` + `manifest.json` |
| 2 | `ath-atl-finder` | `01_fetcher/*.json` | `src/data/pipeline/02_ath_atl.json` |
| 3 | `time-delta-calculator` | `02_ath_atl.json` | `src/data/pipeline/03_time_delta.json` |
| 4 | `stock-analyst` | `03_time_delta.json` | `src/data/pipeline/04_aggregated_staged.json` |
| 5 | `aggregator` | `04_aggregated_staged.json` | `src/outputs/aggregated.json` |

All output skills (`generate_report.py`, `generate_pptx.py`, `generate_pdf.py`) read from `src/outputs/aggregated.json`.

### Classification thresholds

**Speed label** (by days ATL → ATH):
- `Rocket`: < 1,500 days
- `Fast Mover`: 1,500–2,500 days
- `Steady Climber`: > 2,500 days

**Risk label**: `Conservative` / `Moderate` / `Aggressive` / `Speculative`

### Hooks (`.claude/settings.json`)

- **PreToolUse (Bash)**: Blocks commands containing `rm -rf`, `DROP TABLE`, or `sudo rm`
- **PostToolUse (Write)**: Appends a timestamped line to `src/data/hook_log.txt` after every file write
- **Stop**: Verifies `src/outputs/aggregated.json` exists when the run completes
- **SubagentStop**: Logs which subagent just finished

## API

Uses `yfinance` (free, no key). To switch to Polygon.io for production, update the fetcher agent's `.md` and add `WebFetch(domain:api.polygon.io)` to `.claude/settings.local.json`.

## Do not

- Delete or overwrite files in `src/data/pipeline/` — these are cached API results
- Run `rm -rf` anywhere (blocked by PreToolUse hook)
- Hardcode API keys — use environment variables or `settings.local.json`
