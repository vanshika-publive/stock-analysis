# Stock Analysis Project

## What this project does
Analyzes stocks based on the time gap between their all-time high and all-time low.

## Subagents (run in order per ticker)
1. stock-fetcher → saves to src/data/{ticker}.json
2. ath-atl-finder → reads cache, returns extremes JSON
3. time-delta-calculator → computes days/direction/speed
4. stock-analyst → writes human analysis + risk label

## Output skills to run after aggregation
- xlsx skill → src/outputs/stock_report.xlsx
- pptx skill → src/outputs/stock_deck.pptx
- pdf skill → src/outputs/stock_report.pdf

## API
Uses yfinance (free, no key needed). Switch to Polygon.io for production.

## Do not
- Delete files in src/data/ (cached API results)
- Run rm -rf anywhere
- Hardcode API keys