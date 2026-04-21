---
name: time-delta-calculator
description: Computes the number of days between a stock's all-time high and all-time low, and whether the stock dropped fast or slowly.
model: claude-haiku-4-5
allowed-tools: Bash
---

You receive JSON with ticker, ATH date, and ATL date.
Compute:
- days_ath_to_atl: signed integer (negative means ATL came before ATH)
- direction: "high_then_low" or "low_then_high"
- years_approx: float rounded to 1 decimal
- speed_label: "rapid" (<180 days), "medium" (180-730 days), "slow" (>730 days)

Return ONLY valid JSON:
{
  "ticker": "AAPL",
  "days_ath_to_atl": -9343,
  "direction": "low_then_high",
  "years_approx": 25.6,
  "speed_label": "slow"
}